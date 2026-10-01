import { useEffect, useMemo, useRef, useState } from "react";
import { companies as fetchCompanies, type Company, type Prefs } from "../api";
import { I, Mark } from "../icons";
import type { Thread } from "../store";

export type View = "chat" | "companies" | "sectors";

/* ---------------------------------------------------------------- sidebar
   Laid out like a familiar chat app: new chat and search at the top, then the
   chat list, which takes all the remaining height and scrolls on its own. */
const DAY = 86_400_000;
function groupThreads(list: Thread[]): [string, Thread[]][] {
  const start = new Date().setHours(0, 0, 0, 0);
  const buckets: [string, (t: number) => boolean][] = [
    ["Today", (t) => t >= start],
    ["Yesterday", (t) => t >= start - DAY && t < start],
    ["Previous 7 days", (t) => t >= start - 7 * DAY && t < start - DAY],
    ["Previous 30 days", (t) => t >= start - 30 * DAY && t < start - 7 * DAY],
    ["Older", (t) => t < start - 30 * DAY],
  ];
  return buckets.map(([label, test]) => [label, list.filter((t) => test(t.updatedAt))] as [string, Thread[]]).filter(([, ts]) => ts.length > 0);
}

export function Sidebar(props: {
  threads: Thread[]; active: string | null; view: View; lensName: string | null; theme: string;
  onNew: () => void; onOpen: (id: string) => void; onDelete: (id: string) => void; onRename: (id: string, title: string) => void;
  onView: (v: View) => void; onCompany: () => void; onTheme: () => void; onClose: () => void;
}) {
  const [filter, setFilter] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const list = useMemo(() => {
    const s = filter.trim().toLowerCase();
    if (!s) return props.threads;
    return props.threads.filter((t) => t.title.toLowerCase().includes(s) || t.messages.some((m) => m.role === "user" && m.text.toLowerCase().includes(s)));
  }, [props.threads, filter]);
  const groups = groupThreads(list);
  const commit = (id: string) => {
    if (draft.trim()) props.onRename(id, draft.trim().slice(0, 80));
    setEditing(null);
  };
  return (
    <aside className="rail" aria-label="Chats">
      <div className="rail-head">
        <button className="brand" onClick={props.onNew} aria-label="Pramana, new chat">
          <Mark size={28} />
          <span className="brand-word">Pramana</span>
        </button>
        <button className="icon-btn" onClick={props.onClose} aria-label="Close sidebar" title="Close sidebar"><I.sidebar /></button>
      </div>
      <div className="rail-top">
        <button className="rail-item strong" onClick={props.onNew}><I.edit />New chat</button>
        <label className="rail-search">
          <I.search />
          <input placeholder="Search chats" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Search chats" />
          {filter && <button onClick={() => setFilter("")} aria-label="Clear search"><I.x /></button>}
        </label>
        <button className={"rail-item" + (props.view === "companies" ? " active" : "")} onClick={() => props.onView("companies")}><I.building />Companies</button>
        <button className={"rail-item" + (props.view === "sectors" ? " active" : "")} onClick={() => props.onView("sectors")}><I.grid />Sectors</button>
      </div>
      <div className="threads">
        {props.threads.length === 0 && <div className="threads-empty">Your chats will appear here. They are kept in this browser only.</div>}
        {props.threads.length > 0 && groups.length === 0 && <div className="threads-empty">No chats match “{filter}”.</div>}
        {groups.map(([g, ts]) => (
          <div key={g} className="thread-group">
            <div className="thread-g">{g}</div>
            {ts.map((t) => (
              <div key={t.id} className={"thread" + (t.id === props.active && props.view === "chat" ? " active" : "")} role="button" tabIndex={0}
                   onClick={() => editing !== t.id && props.onOpen(t.id)} onKeyDown={(e) => e.key === "Enter" && editing !== t.id && props.onOpen(t.id)} title={t.title}>
                {editing === t.id ? (
                  <input className="thread-edit" autoFocus value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={() => commit(t.id)}
                         onClick={(e) => e.stopPropagation()}
                         onKeyDown={(e) => { e.stopPropagation(); if (e.key === "Enter") commit(t.id); if (e.key === "Escape") setEditing(null); }} />
                ) : <span className="thread-title">{t.title}</span>}
                {editing !== t.id && (
                  <span className="thread-tools">
                    <button onClick={(e) => { e.stopPropagation(); setDraft(t.title); setEditing(t.id); }} aria-label="Rename chat" title="Rename"><I.pencil /></button>
                    <button className="del" onClick={(e) => { e.stopPropagation(); props.onDelete(t.id); }} aria-label="Delete chat" title="Delete"><I.trash /></button>
                  </span>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="rail-foot">
        <button className={"me" + (props.lensName ? " on" : "")} onClick={props.onCompany} title="Answers are about this company when you say “we” or “our”">
          <span className="me-ic"><I.building /></span>
          <span className="me-t">
            <span className="me-k">Your company</span>
            <span className="me-v">{props.lensName || "Not set"}</span>
          </span>
        </button>
        <button className="icon-btn" onClick={props.onTheme} aria-label="Switch between light and dark" title={props.theme === "dark" ? "Switch to light" : "Switch to dark"}>
          {props.theme === "dark" ? <I.sun /> : <I.moon />}
        </button>
      </div>
    </aside>
  );
}

/* ---------------------------------------------------------------- composer */
type Suggestion = { from: number; label: string; sub: string };

/* Company-name autocomplete: completes the words being typed against the
   company names (word-start matching). Tab or Enter on a highlighted item accepts it. */
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

export function Composer({ onSend, busy, lensName, onCompany, autoFocus }: {
  onSend: (q: string) => void; busy: boolean; lensName: string | null; onCompany: () => void; autoFocus?: boolean;
}) {
  const [v, setV] = useState("");
  const [sel, setSel] = useState(-1);
  const [dismissed, setDismissed] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  const sugg = useCompanyComplete(v);
  const open = sugg.length > 0 && dismissed !== v;
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
      <textarea ref={ref} rows={1} value={v} maxLength={600} onChange={(e) => setV(e.target.value)}
                placeholder={lensName ? "Ask about your emissions, peers or targets" : "Ask about a company's emissions, peers or targets"}
                onKeyDown={(e) => {
                  if (open && e.key === "ArrowDown") { e.preventDefault(); setSel((x) => Math.min(sugg.length - 1, x + 1)); return; }
                  if (open && e.key === "ArrowUp") { e.preventDefault(); setSel((x) => Math.max(-1, x - 1)); return; }
                  if (open && e.key === "Tab") { e.preventDefault(); accept(sugg[Math.max(0, sel)]); return; }
                  if (open && e.key === "Enter" && sel >= 0) { e.preventDefault(); accept(sugg[sel]); return; }
                  if (open && e.key === "Escape") { setDismissed(v); return; }
                  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
                }} aria-label="Ask a question" aria-autocomplete="list" />
      <div className="composer-bar">
        <button className={"chip-me" + (lensName ? " on" : "")} onClick={onCompany} title="Answers are about this company when you say “we” or “our”">
          <I.building />{lensName ? <>Answering as <b>{lensName}</b></> : "Set your company"}
        </button>
        <button className="send" onClick={send} disabled={!v.trim() || busy} aria-label="Send"><I.send /></button>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- remembered in this chat */
const EMIS: Record<string, string> = { scope12: "Scope 1 and Scope 2", scope1: "Scope 1", scope2: "Scope 2", scope3: "Scope 3", intensity: "emission intensity" };
export function Learned({ prefs, names, onForget }: { prefs: Prefs; names: Record<string, string>; onForget: (k: keyof Prefs) => void }) {
  const chips: { k: keyof Prefs; label: string }[] = [];
  if (prefs.peers?.length) chips.push({ k: "peers", label: `Peers: ${prefs.peers.map((p) => names[p] || p).join(", ")}` });
  if (prefs.emissions) chips.push({ k: "emissions", label: `“Emissions” means ${EMIS[prefs.emissions] || prefs.emissions}` });
  if (prefs.n) chips.push({ k: "n", label: `Lists show the top ${prefs.n}` });
  if (prefs.aliases && Object.keys(prefs.aliases).length)
    chips.push({ k: "aliases", label: Object.entries(prefs.aliases).map(([t, c]) => `“${t}” means ${names[c] || c}`).join(", ") });
  if (!chips.length) return null;
  return (
    <div className="learned-row" aria-label="Remembered in this chat">
      <span className="learned-k">Remembered</span>
      {chips.map((c) => (
        <span className="learned-chip" key={c.k} title="Applies to later questions in this chat">
          {c.label}
          <button onClick={() => onForget(c.k)} aria-label={`Forget: ${c.label}`}><I.x /></button>
        </span>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- home */
const GENERAL = [
  "What are NTPC's GHG emissions?",
  "How does ACC compare with its peers?",
  "Examples of GHG reduction projects from cement companies",
  "Which sector emits the most?",
  "Make an infographic for UltraTech",
  "Top 10 emitters",
];
const PERSONAL = [
  "What are our GHG emissions?",
  "Who are our peers?",
  "How do we compare with our peers?",
  "What are our targets?",
  "What can we learn from our peers?",
  "Make an infographic of our emissions",
];

export function EmptyState({ onAsk, onHover, lensName, onCompany, count }: {
  onAsk: (q: string) => void; onHover?: (q: string) => void; lensName: string | null; onCompany: () => void; count: number | null;
}) {
  const items = lensName ? PERSONAL : GENERAL;
  return (
    <div className="home">
      <h1>{lensName ? `What would you like to know about ${lensName}?` : "What would you like to know?"}</h1>
      <p className="home-sub">
        GHG emissions and climate disclosures of {count ? count.toLocaleString("en-US") : "listed"} Indian companies, as filed in their BRSR for FY 2024-25.
      </p>
      <div className="suggest">
        {items.map((q, i) => (
          <button key={q} className="sg" onClick={() => onAsk(q)} onMouseEnter={() => onHover?.(q)} onFocus={() => onHover?.(q)} style={{ animation: `rise .45s ${i * 45}ms both` }}>
            <span>{q}</span><I.arrow />
          </button>
        ))}
      </div>
      {!lensName && (
        <p className="home-tip">
          <button className="linkish" onClick={onCompany}>Set your company</button> to ask about “our emissions” or “our peers” without naming it each time.
        </p>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- thinking */
export function Thinking() {
  return (
    <div className="thinking delayed" aria-live="polite" aria-label="Working on it">
      <span className="dots"><i /><i /><i /></span>
    </div>
  );
}

/* ---------------------------------------------------------------- company picker */
export function CompanyPicker({ onClose, onPick, current }: { onClose: () => void; onPick: (id: string | null, name?: string) => void; current: string | null }) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const [cos, setCos] = useState<Company[]>([]);
  useEffect(() => { fetchCompanies().then(setCos).catch(() => {}); }, []);
  const items = useMemo(() => {
    const s = q.trim().toLowerCase();
    const score = (name: string) => {
      const n = name.toLowerCase();
      if (!s) return 1;
      if (n.startsWith(s)) return 3;
      if (n.split(/\s+/).some((w) => w.startsWith(s))) return 2;
      return n.includes(s) ? 1 : 0;
    };
    return cos.map((c) => ({ c, sc: score(c.name) })).filter((x) => x.sc > 0)
      .sort((a, b) => b.sc - a.sc || a.c.name.localeCompare(b.c.name)).slice(0, 60).map((x) => x.c);
  }, [q, cos]);
  useEffect(() => setSel(0), [q]);
  const go = (i: number) => { const c = items[i]; if (c) { onPick(c.id, c.short); onClose(); } };
  return (
    <div className="pal-scrim" onClick={onClose}>
      <div className="pal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Your company">
        <div className="pal-h">
          <div>
            <div className="pal-t">Your company</div>
            <div className="pal-s">Answers will be about this company when you say “we” or “our”. It is saved only in this browser.</div>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><I.x /></button>
        </div>
        <input autoFocus placeholder="Search for a company" value={q} onChange={(e) => setQ(e.target.value)}
               onKeyDown={(e) => {
                 if (e.key === "Escape") onClose();
                 if (e.key === "ArrowDown") { e.preventDefault(); setSel((x) => Math.min(items.length - 1, x + 1)); }
                 if (e.key === "ArrowUp") { e.preventDefault(); setSel((x) => Math.max(0, x - 1)); }
                 if (e.key === "Enter") go(sel);
               }} />
        <div className="pal-list">
          {items.map((c, i) => (
            <div key={c.id} className={"pal-item" + (i === sel ? " sel" : "") + (c.id === current ? " cur" : "")} onMouseEnter={() => setSel(i)} onClick={() => go(i)}>
              <span className="pal-name">{c.short}</span>
              <small>{c.id === current ? "Selected" : c.sector_name}</small>
            </div>
          ))}
          {cos.length === 0 && <div className="pal-item muted">Loading companies…</div>}
          {cos.length > 0 && items.length === 0 && <div className="pal-item muted">No company matches “{q}”.</div>}
        </div>
        {current && (
          <div className="pal-f"><button className="btn" onClick={() => { onPick(null); onClose(); }}>Stop answering as a company</button></div>
        )}
      </div>
    </div>
  );
}
