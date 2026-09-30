import { useEffect, useMemo, useRef, useState } from "react";
import { companies as fetchCompanies, meta as fetchMeta, type Company, type Meta, type Prefs } from "../api";
import { I, Mark } from "../icons";
import type { Thread } from "../store";

export type View = "chat" | "companies" | "sectors" | "method";

/* ---------------------------------------------------------------- sidebar */
export function Sidebar(props: {
  threads: Thread[]; active: string | null; view: View; lensName: string | null; theme: string; meta: Meta | null;
  onNew: () => void; onOpen: (id: string) => void; onDelete: (id: string) => void; onView: (v: View) => void;
  onLens: () => void; onTheme: () => void; onPalette: () => void; onClose: () => void;
}) {
  const [filter, setFilter] = useState("");
  const list = props.threads.filter((t) => !filter || t.title.toLowerCase().includes(filter.toLowerCase()));
  const today = new Date().setHours(0, 0, 0, 0);
  const groups: [string, Thread[]][] = [
    ["Today", list.filter((t) => t.updatedAt >= today)],
    ["Earlier", list.filter((t) => t.updatedAt < today)],
  ];
  const r = props.meta?.reconciliation;
  return (
    <aside className="rail">
      <div className="rail-head">
        <button className="brand" onClick={props.onNew} aria-label="Pramana home">
          <Mark />
          <span><div className="brand-word">Pramana</div><div className="brand-sub">BRSR · E1 intelligence</div></span>
        </button>
        <button className="icon-btn menu-btn" onClick={props.onClose} aria-label="Close sidebar"><I.menu /></button>
      </div>
      <button className="new-btn" onClick={props.onNew}><span style={{ display: "flex", gap: 8, alignItems: "center" }}><I.plus style={{ width: 16, height: 16 }} />New question</span><span className="kbd">⌘K</span></button>
      <button className={"lens" + (props.lensName ? " on" : "")} onClick={props.onLens} title="Set the company answers are framed around">
        <span className="lens-dot" />
        <span style={{ minWidth: 0 }}>
          <div className="lens-lab">Your company lens</div>
          <div className="lens-val">{props.lensName || "Not set, answers are general"}</div>
        </span>
      </button>
      <nav className="rail-nav">
        <button className={"nav-item" + (props.view === "chat" ? " active" : "")} onClick={() => props.onView("chat")}><I.chat />Ask</button>
        <button className={"nav-item" + (props.view === "companies" ? " active" : "")} onClick={() => props.onView("companies")}><I.building />Companies</button>
        <button className={"nav-item" + (props.view === "sectors" ? " active" : "")} onClick={() => props.onView("sectors")}><I.grid />Sectors</button>
        <button className={"nav-item" + (props.view === "method" ? " active" : "")} onClick={() => props.onView("method")}><I.book />Method and sources</button>
      </nav>
      <div className="rail-sec"><span>Conversations</span><span>{props.threads.length}</span></div>
      {props.threads.length > 6 && <input className="thread-search" placeholder="Search conversations" value={filter} onChange={(e) => setFilter(e.target.value)} />}
      <div className="threads">
        {props.threads.length === 0 && <div className="muted" style={{ fontSize: 13, padding: "6px 10px" }}>Your questions are remembered in this browser only.</div>}
        {groups.map(([g, ts]) => ts.length > 0 && (
          <div key={g}>
            <div className="rail-sec" style={{ padding: "10px 8px 4px" }}>{g}</div>
            {ts.map((t) => (
              <div key={t.id} className={"thread" + (t.id === props.active && props.view === "chat" ? " active" : "")} onClick={() => props.onOpen(t.id)} role="button" tabIndex={0}
                   onKeyDown={(e) => e.key === "Enter" && props.onOpen(t.id)}>
                <span className="thread-title">{t.title}</span>
                <button className="x" onClick={(e) => { e.stopPropagation(); props.onDelete(t.id); }} aria-label="Delete conversation"><I.x style={{ width: 13, height: 13 }} /></button>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="rail-foot">
        <button className="verify" onClick={() => props.onView("method")}>
          <I.shield className="verify-seal" />
          <span><strong>{r ? `${r.matched} of ${r.total}` : "597 of 597"}</strong> report figures reproduced from raw data</span>
        </button>
        <div className="rail-row">
          <span>{props.meta ? `${props.meta.dataset.n_companies} companies · FY 2024-25` : "Loading dataset"}</span>
          <button className="icon-btn" onClick={props.onTheme} aria-label="Toggle theme" title={`Theme: ${props.theme}`}>{props.theme === "dark" ? <I.moon /> : <I.sun />}</button>
        </div>
      </div>
    </aside>
  );
}

/* ---------------------------------------------------------------- composer */
const PLACEHOLDERS = [
  "Ask about any of the 982 companies, sectors or the E1 report",
  "What are Tata Steel's Scope 1 emissions?",
  "How does ACC compare with its peers?",
  "Best practices for GHG reduction projects in cement",
  "Which companies mention green hydrogen?",
];

type Suggestion = { from: number; label: string; sub: string };

/* Company-name autocomplete: completes the words being typed against the 982
   company names (word-start matching), so names are spelled the way the
   dataset knows them. Tab or Enter on a highlighted item accepts it. */
function useCompanyComplete(value: string) {
  const [cos, setCos] = useState<Company[]>([]);
  useEffect(() => { fetchCompanies().then(setCos).catch(() => {}); }, []);
  return useMemo<Suggestion[]>(() => {
    if (!cos.length || /\s$/.test(value)) return [];
    const words = value.split(/\s+/);
    for (let n = Math.min(3, words.length); n >= 1; n--) {
      const frag = words.slice(-n).join(" ").replace(/[^\w&.' -]/g, "").toLowerCase();
      if (frag.replace(/\s/g, "").length < 3) continue;
      const hits = cos
        .map((c) => {
          const nm = c.short.toLowerCase();
          const at = nm.startsWith(frag) ? 0 : nm.includes(" " + frag) ? 1 : -1;
          return { c, at };
        })
        .filter((x) => x.at >= 0 && x.c.short.toLowerCase() !== frag)
        .sort((a, b) => a.at - b.at || a.c.short.length - b.c.short.length || a.c.short.localeCompare(b.c.short))
        .slice(0, 5);
      if (hits.length) {
        const from = value.length - words.slice(-n).join(" ").length;
        return hits.map((h) => ({ from, label: h.c.short, sub: h.c.sector_name }));
      }
    }
    return [];
  }, [value, cos]);
}

export function Composer({ onSend, busy, lensName, autoFocus }: { onSend: (q: string) => void; busy: boolean; lensName: string | null; autoFocus?: boolean }) {
  const [v, setV] = useState("");
  const [ph, setPh] = useState(0);
  const [sel, setSel] = useState(-1);
  const [dismissed, setDismissed] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  const sugg = useCompanyComplete(v);
  const open = sugg.length > 0 && dismissed !== v;
  useEffect(() => {
    const t = setInterval(() => setPh((p) => (p + 1) % PLACEHOLDERS.length), 3800);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    if (!ref.current) return;
    ref.current.style.height = "auto";
    ref.current.style.height = Math.min(200, ref.current.scrollHeight) + "px";
  }, [v]);
  useEffect(() => { if (autoFocus) ref.current?.focus(); }, [autoFocus]);
  useEffect(() => { setSel(-1); }, [v]);
  const send = () => {
    const q = v.trim();
    if (!q || busy) return;
    onSend(q);
    setV("");
  };
  const accept = (s: Suggestion) => {
    const next = v.slice(0, s.from) + s.label + " ";
    setV(next);
    setDismissed(next);
    ref.current?.focus();
  };
  return (
    <div className="composer">
      {open && (
        <div className="ac" role="listbox" aria-label="Company suggestions">
          {sugg.map((s, i) => (
            <button key={s.label} role="option" aria-selected={i === sel} className={"ac-item" + (i === sel ? " sel" : "")}
                    onMouseDown={(e) => { e.preventDefault(); accept(s); }}>
              <span>{s.label}</span><small>{s.sub}</small>
            </button>
          ))}
          <div className="ac-hint">Tab to complete · Esc to dismiss</div>
        </div>
      )}
      <textarea ref={ref} rows={1} value={v} placeholder={PLACEHOLDERS[ph]} onChange={(e) => setV(e.target.value)} maxLength={600}
                onKeyDown={(e) => {
                  if (open && e.key === "ArrowDown") { e.preventDefault(); setSel((x) => Math.min(sugg.length - 1, x + 1)); return; }
                  if (open && e.key === "ArrowUp") { e.preventDefault(); setSel((x) => Math.max(-1, x - 1)); return; }
                  if (open && e.key === "Tab") { e.preventDefault(); accept(sugg[Math.max(0, sel)]); return; }
                  if (open && e.key === "Enter" && sel >= 0) { e.preventDefault(); accept(sugg[sel]); return; }
                  if (open && e.key === "Escape") { setDismissed(v); return; }
                  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
                }} aria-label="Ask a question" aria-autocomplete="list" />
      <div className="composer-bar">
        <div className="composer-hints">
          {lensName ? <span className="chip-lens" title="Answers use this company for 'we' and 'our'">Lens: {lensName}</span> : <span>No sign-in. Memory stays in this browser.</span>}
          <span className="hide-sm">· Enter to send, Shift+Enter for a new line</span>
        </div>
        <button className="send" onClick={send} disabled={!v.trim() || busy} aria-label="Send"><I.send /></button>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- learned in this conversation */
const EMIS: Record<string, string> = { scope12: "Scope 1+2", scope1: "Scope 1", scope2: "Scope 2", scope3: "Scope 3", intensity: "Scope 1+2 intensity" };
export function Learned({ prefs, names, onForget }: { prefs: Prefs; names: Record<string, string>; onForget: (k: keyof Prefs) => void }) {
  const chips: { k: keyof Prefs; label: string }[] = [];
  if (prefs.peers?.length) chips.push({ k: "peers", label: `Peers: ${prefs.peers.map((p) => names[p] || p).join(", ")}` });
  if (prefs.emissions) chips.push({ k: "emissions", label: `"Emissions" = ${EMIS[prefs.emissions] || prefs.emissions}` });
  if (prefs.n) chips.push({ k: "n", label: `Rankings: top ${prefs.n}` });
  if (prefs.aliases && Object.keys(prefs.aliases).length)
    chips.push({ k: "aliases", label: Object.entries(prefs.aliases).map(([t, c]) => `"${t}" = ${names[c] || c}`).join(", ") });
  if (!chips.length) return null;
  return (
    <div className="learned-row" aria-label="Learned in this conversation">
      <span className="learned-k">Learned here</span>
      {chips.map((c) => (
        <span className="learned-chip" key={c.k} title="Applies to later questions in this conversation">
          {c.label}
          <button onClick={() => onForget(c.k)} aria-label={`Forget ${c.label}`}><I.x /></button>
        </span>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- empty state */
const STARTERS = [
  { k: "Plain data", c: "var(--s1)", q: "What are Tata Steel's Scope 1 and Scope 2 emissions?" },
  { k: "Peer comparison", c: "var(--s2)", q: "How does ACC compare with its peers?" },
  { k: "Best practices", c: "var(--s3)", q: "Best practices for GHG reduction projects in cement" },
  { k: "Sector insight", c: "var(--s4)", q: "Give me an overview of the power sector" },
  { k: "What-if", c: "var(--s7)", q: "What if NTPC cuts Scope 1 by 10%?" },
  { k: "Search disclosures", c: "var(--s5)", q: "Which companies mention green hydrogen?" },
];

export function EmptyState({ onAsk, onHover, meta, sectorsTotal }: { onAsk: (q: string) => void; onHover?: (q: string) => void; meta: Meta | null; sectorsTotal: number | null }) {
  const r = meta?.reconciliation;
  return (
    <div className="hero">
      <div className="eyebrow">BRSR FY 2024-25 · Theme E1 · GHG emissions and climate risk</div>
      <h1>Ask the record. Get the <em>proof</em>.</h1>
      <p className="lede">
        Pramana answers questions on the climate disclosures of India's top listed companies using only the IIMB dataset.
        Every figure links to the exact workbook cell, rating or report page it came from. If it is not in the data, it says so.
      </p>
      <div className="facts">
        <div className="fact"><div className="fact-v">{meta ? meta.dataset.n_companies : 982}</div><div className="fact-l">companies with BRSR filings</div></div>
        <div className="fact"><div className="fact-v">{meta ? meta.dataset.n_sectors : 22}</div><div className="fact-l">NSE sectors benchmarked</div></div>
        <div className="fact"><div className="fact-v">{sectorsTotal ? `${(sectorsTotal / 1e9).toFixed(2)}B` : "1.31B"}</div><div className="fact-l">tCO₂e Scope 1+2 disclosed</div></div>
        <div className="fact"><div className="fact-v">{r ? `${r.matched}/${r.total}` : "597/597"}</div><div className="fact-l">report figures reproduced</div></div>
      </div>
      <div className="starters-h"><h2>Start with a question</h2><span className="muted" style={{ fontSize: 12.5 }}>or press ⌘K to find a company</span></div>
      <div className="starters">
        {STARTERS.map((s, i) => (
          <button key={s.k} className="starter" onClick={() => onAsk(s.q)} onMouseEnter={() => onHover?.(s.q)} onFocus={() => onHover?.(s.q)} style={{ animation: `rise .5s ${i * 60}ms both` }}>
            <span className="starter-k"><i style={{ background: s.c }} />{s.k}</span>
            <span className="starter-q">{s.q}</span>
            <span className="starter-go">Ask <I.arrow style={{ width: 13, height: 13 }} /></span>
          </button>
        ))}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- thinking */
const STEPS = ["Understanding the question", "Linking companies, sectors and metrics", "Computing from 982 filings", "Composing with citations"];
export function Thinking() {
  const [s, setS] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setS((x) => Math.min(STEPS.length - 1, x + 1)), 170);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="thinking delayed" aria-live="polite">
      {STEPS.map((t, i) => (
        <div key={t} className={"think-row" + (i < s ? " done" : i === s ? " active" : "")}><span className="think-dot" />{t}</div>
      ))}
      <div className="skeleton" style={{ width: "62%", marginTop: 6 }} />
      <div className="skeleton" style={{ width: "88%" }} />
    </div>
  );
}

/* ---------------------------------------------------------------- command palette */
type Item = { group: string; label: string; sub?: string; run: () => void; actions?: { label: string; run: () => void }[] };

export function Palette({ onClose, onAsk, onLens, mode, threads, onOpenThread }: {
  onClose: () => void; onAsk: (q: string) => void; onLens: (id: string | null, name?: string) => void; mode: "search" | "lens";
  threads: Thread[]; onOpenThread: (id: string) => void;
}) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const [cos, setCos] = useState<Company[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  useEffect(() => { fetchCompanies().then(setCos); fetchMeta().then(setMeta); }, []);
  const items: Item[] = useMemo(() => {
    const s = q.trim().toLowerCase();
    const score = (name: string) => {
      const n = name.toLowerCase();
      if (!s) return 1;
      if (n.startsWith(s)) return 3;
      if (n.split(/\s+/).some((w) => w.startsWith(s))) return 2;
      return n.includes(s) ? 1 : 0;
    };
    const out: Item[] = [];
    if (mode === "lens") {
      out.push({ group: "Lens", label: "Clear lens (general answers)", run: () => onLens(null) });
      cos.map((c) => ({ c, sc: score(c.name) })).filter((x) => x.sc > 0).sort((a, b) => b.sc - a.sc || a.c.name.localeCompare(b.c.name)).slice(0, 40)
        .forEach(({ c }) => out.push({ group: "Companies", label: c.short, sub: c.sector_name, run: () => onLens(c.id, c.short) }));
      return out;
    }
    if (s) out.push({ group: "Ask", label: `Ask: ${q.trim()}`, run: () => onAsk(q.trim()) });
    cos.map((c) => ({ c, sc: score(c.name) })).filter((x) => x.sc > 0).sort((a, b) => b.sc - a.sc || a.c.name.localeCompare(b.c.name)).slice(0, s ? 12 : 6)
      .forEach(({ c }) => out.push({
        group: "Companies", label: c.short, sub: c.sector_name, run: () => onAsk(`Show ${c.short}'s E1 profile`),
        actions: [
          { label: "Peers", run: () => onAsk(`How does ${c.short} compare with its peers?`) },
          { label: "Set lens", run: () => onLens(c.id, c.short) },
        ],
      }));
    (meta?.sectors || []).filter((x) => score(x.name) > 0 || score(x.short) > 0).slice(0, s ? 6 : 4)
      .forEach((x) => out.push({ group: "Sectors", label: x.name, sub: `${x.n} companies`, run: () => onAsk(`Give me an overview of the ${x.name} sector`) }));
    threads.filter((t) => s && t.title.toLowerCase().includes(s)).slice(0, 5)
      .forEach((t) => out.push({ group: "Conversations", label: t.title, run: () => onOpenThread(t.id) }));
    return out;
  }, [q, cos, meta, mode, threads]);
  useEffect(() => setSel(0), [q]);
  const go = (i: number) => { const it = items[i]; if (it) { it.run(); onClose(); } };
  let lastGroup = "";
  return (
    <div className="pal-scrim" onClick={onClose}>
      <div className="pal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Search">
        <input autoFocus placeholder={mode === "lens" ? "Which company are you from? (optional, stays in this browser)" : "Search companies, sectors, or type a question"} value={q}
               onChange={(e) => setQ(e.target.value)}
               onKeyDown={(e) => {
                 if (e.key === "Escape") onClose();
                 if (e.key === "ArrowDown") { e.preventDefault(); setSel((x) => Math.min(items.length - 1, x + 1)); }
                 if (e.key === "ArrowUp") { e.preventDefault(); setSel((x) => Math.max(0, x - 1)); }
                 if (e.key === "Enter") go(sel);
               }} />
        <div className="pal-list">
          {items.map((it, i) => {
            const head = it.group !== lastGroup ? (lastGroup = it.group) : null;
            return (
              <div key={it.group + it.label + i}>
                {head && <div className="pal-group">{head}</div>}
                <div className={"pal-item" + (i === sel ? " sel" : "")} onMouseEnter={() => setSel(i)} onClick={() => go(i)}>
                  <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{it.label} {it.sub && <small>{it.sub}</small>}</span>
                  {it.actions && <span className="pal-actions">{it.actions.map((a) => <button key={a.label} onClick={(e) => { e.stopPropagation(); a.run(); onClose(); }}>{a.label}</button>)}</span>}
                </div>
              </div>
            );
          })}
          {items.length === 0 && <div className="pal-item muted">No match among the 982 companies.</div>}
        </div>
      </div>
    </div>
  );
}
