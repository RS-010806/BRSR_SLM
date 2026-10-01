import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { ask as apiAsk, companies as fetchCompanies, meta as fetchMeta, prefetch as apiPrefetch, resolveShare, type Ctx, type Meta, type Prefs } from "./api";
import { AnswerView } from "./components/Answer";
import { CompanyPicker, Composer, EmptyState, Learned, Sidebar, Thinking, type View } from "./components/Shell";
import { I } from "./icons";
import { getLens, getTheme, loadThreads, newId, saveThreads, setLens as storeLens, setTheme as storeTheme, type Msg, type Thread } from "./store";
import { currentTheme, toast } from "./ui";

const CompaniesPage = lazy(() => import("./pages/Pages").then((m) => ({ default: m.CompaniesPage })));
const SectorsPage = lazy(() => import("./pages/Pages").then((m) => ({ default: m.SectorsPage })));

function viewFromHash(): View {
  const h = window.location.hash.replace("#/", "");
  return h === "companies" || h === "sectors" ? h : "chat";
}
const RAIL = "pramana.rail";
const railPref = () => { try { return localStorage.getItem(RAIL) !== "closed"; } catch { return true; } };

export default function App() {
  const [threads, setThreads] = useState<Thread[]>(() => loadThreads());
  const [active, setActive] = useState<string | null>(null);
  const [view, setView] = useState<View>(viewFromHash());
  const [meta, setMeta] = useState<Meta | null>(null);
  const [lens, setLensState] = useState<string | null>(() => getLens());
  const [names, setNames] = useState<Record<string, string>>({});
  const [theme, setThemeState] = useState(getTheme());
  const [picker, setPicker] = useState(false);
  const [railOpen, setRailOpen] = useState(false);           // drawer on small screens
  const [railShown, setRailShown] = useState(railPref);       // column on large screens
  const [busy, setBusy] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const booted = useRef(false);

  useEffect(() => {
    fetchMeta().then(setMeta).catch(() => {});
    fetchCompanies().then((cs) => setNames(Object.fromEntries(cs.map((c) => [c.id, c.short])))).catch(() => {});
  }, []);
  const lensName = lens ? names[lens] || null : null;
  useEffect(() => { saveThreads(threads); }, [threads]);
  useEffect(() => {
    const f = () => setView(viewFromHash());
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);

  const thread = threads.find((t) => t.id === active) || null;
  // The context every question in this thread is asked with. Prefetch uses the
  // exact same function, so a prefetched answer is the answer a click would get.
  const ctxFor = useCallback((t: Thread | null): Ctx => ({ ...(t?.context || {}), lens: lens || null }), [lens]);

  const goView = (v: View) => {
    setView(v);
    window.history.pushState(null, "", v === "chat" ? "/" : `/#/${v}`);
    setRailOpen(false);
  };
  const toggleRail = () => {
    if (window.matchMedia("(max-width: 980px)").matches) { setRailOpen((x) => !x); return; }
    setRailShown((x) => {
      try { localStorage.setItem(RAIL, x ? "closed" : "open"); } catch { /* not persisted */ }
      return !x;
    });
  };

  const scrollToEnd = () => requestAnimationFrame(() => {
    const el = scrollRef.current;
    if (!el) return;
    const answers = el.querySelectorAll(".msg-user");
    const last = answers[answers.length - 1] as HTMLElement | undefined;
    if (last) el.scrollTo({ top: last.offsetTop - 70, behavior: "smooth" });
  });

  const applyLens = (id: string | null) => {
    storeLens(id);
    setLensState(id);
  };

  const send = useCallback(async (q: string, forceNew = false, ctxOverride?: Ctx) => {
    if (busy) return;
    setView("chat");
    if (window.location.hash || window.location.pathname !== "/") window.history.pushState(null, "", "/");
    setRailOpen(false);
    let id = forceNew ? null : active;
    let base: Thread | undefined = id ? threads.find((t) => t.id === id) : undefined;
    if (!base) {
      id = newId();
      base = { id, title: q.slice(0, 70), createdAt: Date.now(), updatedAt: Date.now(), messages: [], context: {} };
    }
    const ctx: Ctx = ctxOverride ? { ...ctxOverride, lens: ctxOverride.lens ?? lens ?? null } : ctxFor(base);
    const pendingMsg: Msg = { role: "assistant", q, at: Date.now(), pending: true };
    const next: Thread = { ...base, updatedAt: Date.now(), messages: [...base.messages, { role: "user", text: q, at: Date.now() }, pendingMsg] };
    setThreads((ts) => [next, ...ts.filter((t) => t.id !== next.id)]);
    setActive(next.id);
    setBusy(true);
    scrollToEnd();
    try {
      const a = await apiAsk(q, ctx);
      // the answer can set or clear your company ("my company is ...", "clear my company")
      if (a.context?.lens === "") applyLens(null);
      else if (a.context?.lens && a.context.lens !== lens) applyLens(a.context.lens);
      setThreads((ts) => ts.map((t) => t.id !== next.id ? t : {
        ...t, updatedAt: Date.now(), context: { ...a.context, lens: undefined },
        messages: t.messages.map((m) => (m.role === "assistant" && m.pending ? { role: "assistant", q, answer: a, at: Date.now(), ctxUsed: ctx } as any : m)),
      }));
    } catch (err: any) {
      setThreads((ts) => ts.map((t) => t.id !== next.id ? t : {
        ...t, messages: t.messages.map((m) => (m.role === "assistant" && m.pending ? { role: "assistant", q, error: err?.message || "Something went wrong", at: Date.now() } : m)),
      }));
    } finally {
      setBusy(false);
    }
  }, [active, threads, lens, busy, ctxFor]);

  const prefetchInThread = useCallback((q: string) => apiPrefetch(q, ctxFor(thread)), [thread, ctxFor]);
  const prefetchFresh = useCallback((q: string) => apiPrefetch(q, { lens: lens || null }), [lens]);

  // share links: /s/<code> (short, stored) or /?q=...&ctx=... (self-contained)
  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    const u = new URL(window.location.href);
    const m = u.pathname.match(/^\/s\/([A-Za-z0-9]{4,16})$/);
    if (m) {
      resolveShare(m[1]).then((s) => {
        window.history.replaceState(null, "", "/");
        if (s) send(s.q, true, s.ctx);
        else toast("That link is no longer available.");
      });
      return;
    }
    const q = u.searchParams.get("q");
    if (q) {
      let ctx: Ctx | undefined;
      const c = u.searchParams.get("ctx");
      if (c) { try { ctx = JSON.parse(decodeURIComponent(escape(atob(c)))); } catch { ctx = undefined; } }
      window.history.replaceState(null, "", "/");
      setTimeout(() => send(q, true, ctx), 30);
    }
  }, [send]);

  const newChat = () => { setActive(null); goView("chat"); };
  const pickCompany = (id: string | null, name?: string) => {
    applyLens(id);
    toast(id ? `Answering as ${name}. Try “What are our GHG emissions?”` : "No longer answering as a company.");
  };
  const toggleTheme = () => {
    const nxt = currentTheme() === "dark" ? "light" : "dark";
    storeTheme(nxt);
    setThemeState(nxt);
  };
  // What a chat has been told to remember is held in the browser: removing it just edits the chat's context.
  const forget = (key: keyof Prefs) => {
    if (!thread) return;
    setThreads((ts) => ts.map((t) => {
      if (t.id !== thread.id) return t;
      const prefs = { ...(t.context.prefs || {}) } as any;
      delete prefs[key];
      return { ...t, context: { ...t.context, prefs } };
    }));
    toast("Forgotten for this chat.");
  };
  const shownTheme = theme === "system" ? currentTheme() : theme;
  const title = view === "chat" ? (thread ? thread.title : "") : view === "companies" ? "Companies" : "Sectors";

  return (
    <div className={"shell" + (railOpen ? " rail-open" : "") + (railShown ? "" : " rail-closed")}>
      <Sidebar threads={threads} active={active} view={view} lensName={lensName} theme={shownTheme}
               onNew={newChat} onOpen={(id) => { setActive(id); goView("chat"); }}
               onDelete={(id) => { setThreads((ts) => ts.filter((t) => t.id !== id)); if (active === id) setActive(null); }}
               onRename={(id, t) => setThreads((ts) => ts.map((x) => (x.id === id ? { ...x, title: t } : x)))}
               onView={goView} onCompany={() => { setPicker(true); setRailOpen(false); }} onTheme={toggleTheme} onClose={toggleRail} />
      <main className="main">
        <div className={"topbar" + (scrolled ? " scrolled" : "")}>
          <div className="topbar-l">
            <button className="icon-btn rail-toggle" onClick={toggleRail} aria-label="Open sidebar" title="Open sidebar"><I.sidebar /></button>
            <button className="icon-btn rail-toggle" onClick={newChat} aria-label="New chat" title="New chat"><I.edit /></button>
            <span className="topbar-title">{title}</span>
          </div>
        </div>
        <div className="scroll" ref={scrollRef} onScroll={(e) => setScrolled((e.target as HTMLElement).scrollTop > 8)}>
          <div className="col">
            <Suspense fallback={<div className="page"><div className="skeleton" style={{ width: "40%", height: 28 }} /></div>}>
              {view === "companies" && <CompaniesPage onAsk={(q) => send(q, true)} meta={meta} />}
              {view === "sectors" && <SectorsPage onAsk={(q) => send(q, true)} />}
            </Suspense>
            {view === "chat" && !thread && <EmptyState onAsk={(q) => send(q, true)} onHover={prefetchFresh} lensName={lensName} onCompany={() => setPicker(true)} count={meta?.companies ?? null} />}
            {view === "chat" && thread && (
              <div className="conv">
                {thread.messages.map((m, i) => m.role === "user"
                  ? <div className="msg-user" key={i}><div className="bubble">{m.text}</div></div>
                  : m.pending ? <Thinking key={i} />
                  : m.error ? <div key={i} className="note scope"><I.alert /><div>{m.error}. <button className="linkish" onClick={() => send(m.q)}>Try again</button></div></div>
                  : <AnswerView key={i} index={i} a={m.answer!} q={m.q} ctx={(m as any).ctxUsed} ask={(q) => send(q)} prefetch={prefetchInThread} pickCompany={() => setPicker(true)} />)}
              </div>
            )}
          </div>
        </div>
        {view === "chat" && (
          <div className="composer-wrap">
            <div className="col">
              {thread?.context?.prefs && <Learned prefs={thread.context.prefs} names={names} onForget={forget} />}
              <Composer onSend={(q) => send(q)} busy={busy} lensName={lensName} onCompany={() => setPicker(true)} autoFocus={!thread} />
              <div className="disclaimer">Figures are as disclosed by companies in their BRSR filings for FY 2024-25.</div>
            </div>
          </div>
        )}
      </main>
      {railOpen && <div className="drawer-scrim rail-scrim" onClick={() => setRailOpen(false)} />}
      {picker && <CompanyPicker onClose={() => setPicker(false)} onPick={pickCompany} current={lens} />}
    </div>
  );
}
