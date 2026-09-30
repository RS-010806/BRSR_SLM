import { useCallback, useEffect, useRef, useState } from "react";
import { ask as apiAsk, companies as fetchCompanies, meta as fetchMeta, type Ctx, type Meta } from "./api";
import { AnswerView } from "./components/Answer";
import { Composer, EmptyState, Palette, Sidebar, Thinking, type View } from "./components/Shell";
import { I } from "./icons";
import { CompaniesPage, MethodPage, SectorsPage } from "./pages/Pages";
import { getLens, getTheme, loadThreads, newId, saveThreads, setLens as storeLens, setTheme as storeTheme, type Msg, type Thread } from "./store";
import { toast } from "./ui";

const MIN_THINK_MS = 520;

function viewFromHash(): View {
  const h = window.location.hash.replace("#/", "");
  return h === "companies" || h === "sectors" || h === "method" ? h : "chat";
}

export default function App() {
  const [threads, setThreads] = useState<Thread[]>(() => loadThreads());
  const [active, setActive] = useState<string | null>(null);
  const [view, setView] = useState<View>(viewFromHash());
  const [meta, setMeta] = useState<Meta | null>(null);
  const [sectorsTotal, setSectorsTotal] = useState<number | null>(null);
  const [lens, setLensState] = useState<string | null>(() => getLens());
  const [lensName, setLensName] = useState<string | null>(null);
  const [theme, setThemeState] = useState(getTheme());
  const [palette, setPalette] = useState<null | "search" | "lens">(null);
  const [railOpen, setRailOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const booted = useRef(false);

  useEffect(() => { fetchMeta().then(setMeta).catch(() => {}); fetch("/api/sectors").then((r) => r.json()).then((s) => setSectorsTotal(s.reduce((a: number, x: any) => a + x.s12, 0))).catch(() => {}); }, []);
  useEffect(() => {
    if (!lens) return setLensName(null);
    fetchCompanies().then((cs) => setLensName(cs.find((c) => c.id === lens)?.short || null));
  }, [lens]);
  useEffect(() => { saveThreads(threads); }, [threads]);
  useEffect(() => {
    const f = () => setView(viewFromHash());
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((p) => (p ? null : "search")); }
    };
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  }, []);

  const thread = threads.find((t) => t.id === active) || null;

  const goView = (v: View) => {
    setView(v);
    window.history.pushState(null, "", v === "chat" ? window.location.pathname + window.location.search : `#/${v}`);
    setRailOpen(false);
  };

  const scrollToEnd = () => requestAnimationFrame(() => {
    const el = scrollRef.current;
    if (!el) return;
    const answers = el.querySelectorAll(".msg-user");
    const last = answers[answers.length - 1] as HTMLElement | undefined;
    if (last) el.scrollTo({ top: last.offsetTop - 70, behavior: "smooth" });
  });

  const send = useCallback(async (q: string, forceNew = false, ctxOverride?: Ctx) => {
    if (busy) return;
    setView("chat");
    if (window.location.hash) window.history.pushState(null, "", window.location.pathname);
    setRailOpen(false);
    let id = forceNew ? null : active;
    let base: Thread | undefined = id ? threads.find((t) => t.id === id) : undefined;
    if (!base) {
      id = newId();
      base = { id, title: q.slice(0, 70), createdAt: Date.now(), updatedAt: Date.now(), messages: [], context: {} };
    }
    const ctx: Ctx = { ...(ctxOverride || base.context || {}), lens: lens || null };
    const pendingMsg: Msg = { role: "assistant", q, at: Date.now(), pending: true };
    const next: Thread = { ...base, updatedAt: Date.now(), messages: [...base.messages, { role: "user", text: q, at: Date.now() }, pendingMsg] };
    setThreads((ts) => [next, ...ts.filter((t) => t.id !== next.id)]);
    setActive(next.id);
    setBusy(true);
    scrollToEnd();
    const t0 = performance.now();
    try {
      const a = await apiAsk(q, ctx);
      const wait = MIN_THINK_MS - (performance.now() - t0);
      if (wait > 0) await new Promise((r) => setTimeout(r, wait));
      if (a.context?.lens && a.context.lens !== lens) {
        storeLens(a.context.lens);
        setLensState(a.context.lens);
        toast("Company lens set. Answers will be framed around it.");
      }
      setThreads((ts) => ts.map((t) => t.id !== next.id ? t : {
        ...t, updatedAt: Date.now(), context: { ...a.context, lens: undefined },
        messages: t.messages.map((m) => (m === pendingMsg || (m.role === "assistant" && m.pending) ? { role: "assistant", q, answer: a, at: Date.now(), ctxUsed: ctx } as any : m)),
      }));
    } catch (err: any) {
      setThreads((ts) => ts.map((t) => t.id !== next.id ? t : {
        ...t, messages: t.messages.map((m) => (m.role === "assistant" && m.pending ? { role: "assistant", q, error: err?.message || "Something went wrong", at: Date.now() } : m)),
      }));
    } finally {
      setBusy(false);
    }
  }, [active, threads, lens, busy]);

  // share links: /?q=...&ctx=...
  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    const u = new URL(window.location.href);
    const q = u.searchParams.get("q");
    if (q) {
      let ctx: Ctx | undefined;
      const c = u.searchParams.get("ctx");
      if (c) { try { ctx = JSON.parse(decodeURIComponent(escape(atob(c)))); } catch { ctx = undefined; } }
      window.history.replaceState(null, "", u.pathname);
      setTimeout(() => send(q, true, ctx), 50);
    }
  }, [send]);

  const newChat = () => { setActive(null); goView("chat"); };
  const setLensTo = (id: string | null, name?: string) => {
    storeLens(id);
    setLensState(id);
    toast(id ? `Lens set to ${name}. Try "how do we compare with our peers?"` : "Lens cleared. Answers are general.");
  };
  const toggleTheme = () => {
    const cur = theme === "system" ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : theme;
    const nxt = cur === "dark" ? "light" : "dark";
    storeTheme(nxt);
    setThemeState(nxt);
  };

  return (
    <div className={"shell" + (railOpen ? " rail-open" : "")}>
      <Sidebar threads={threads} active={active} view={view} lensName={lensName} theme={theme === "system" ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : theme} meta={meta}
               onNew={newChat} onOpen={(id) => { setActive(id); goView("chat"); }} onDelete={(id) => { setThreads((ts) => ts.filter((t) => t.id !== id)); if (active === id) setActive(null); }}
               onView={goView} onLens={() => setPalette("lens")} onTheme={toggleTheme} onPalette={() => setPalette("search")} onClose={() => setRailOpen(false)} />
      <main className="main">
        <div className={"topbar" + (scrolled ? " scrolled" : "")}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", minWidth: 0 }}>
            <button className="icon-btn menu-btn" onClick={() => setRailOpen(true)} aria-label="Open sidebar"><I.menu /></button>
            <span className="topbar-title">{view === "chat" ? (thread ? thread.title : "New question") : view === "companies" ? "Companies" : view === "sectors" ? "Sectors" : "Method and sources"}</span>
          </div>
          <div className="top-actions">
            <button className="pill hide-sm" onClick={() => setPalette("search")}><I.search />Find a company <span className="kbd">⌘K</span></button>
            <button className="pill" onClick={() => setPalette("lens")}><I.target />{lensName ? lensName : "Set lens"}</button>
          </div>
        </div>
        <div className="scroll" ref={scrollRef} onScroll={(e) => setScrolled((e.target as HTMLElement).scrollTop > 8)}>
          <div className="col">
            {view === "companies" && <CompaniesPage onAsk={(q) => send(q, true)} meta={meta} />}
            {view === "sectors" && <SectorsPage onAsk={(q) => send(q, true)} />}
            {view === "method" && <MethodPage meta={meta} onAsk={(q) => send(q, true)} />}
            {view === "chat" && !thread && <EmptyState onAsk={(q) => send(q, true)} meta={meta} sectorsTotal={sectorsTotal} />}
            {view === "chat" && thread && (
              <div className="conv">
                {thread.messages.map((m, i) => m.role === "user"
                  ? <div className="msg-user" key={i}><div className="bubble">{m.text}</div></div>
                  : m.pending ? <Thinking key={i} />
                  : m.error ? <div key={i} className="note scope"><I.alert /><div>{m.error}. <button className="linkish" onClick={() => send(m.q)}>Try again</button></div></div>
                  : <AnswerView key={i} index={i} a={m.answer!} q={m.q} ctx={(m as any).ctxUsed} ask={(q) => send(q)} />)}
              </div>
            )}
          </div>
        </div>
        {view === "chat" && (
          <div className="composer-wrap">
            <div className="col">
              <Composer onSend={(q) => send(q)} busy={busy} lensName={lensName} autoFocus={!thread} />
              <div className="disclaimer">Answers come only from the IIMB E1 dataset and report. Figures are as filed by companies for FY 2024-25.</div>
            </div>
          </div>
        )}
      </main>
      {railOpen && <div className="drawer-scrim" style={{ zIndex: 45 }} onClick={() => setRailOpen(false)} />}
      {palette && <Palette mode={palette} onClose={() => setPalette(null)} onAsk={(q) => send(q, true)} onLens={setLensTo} threads={threads} onOpenThread={(id) => { setActive(id); goView("chat"); }} />}
    </div>
  );
}
