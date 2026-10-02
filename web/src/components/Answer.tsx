import { useEffect, useState } from "react";
import { createShare, sendFeedback, type Answer, type Citation, type Ctx } from "../api";
import { downloadAnswer } from "../exporting";
import { I } from "../icons";
import { AnswerCtx, Rich, toast, useHoverPrefetch } from "../ui";
import { BlockView } from "./blocks";

/* What a source is, in words an end user recognises: a company's own disclosure,
   or arithmetic over disclosed figures. */
export function citeWhere(c: Citation): string {
  if (c.kind === "filing") return `BRSR ${c.fy}`;
  return c.kind === "computed" ? "Calculated" : "Note";
}
export function citeWhat(c: Citation): string {
  if (c.kind === "filing") return `${c.company}: ${c.item}`;
  return c.label;
}

const srcValue = (c: Citation) => (c.kind === "filing" && typeof c.value === "string" && c.value.length <= 22 ? c.value : "");

/* ---------------------------------------------------------------- source drawer */
export function Evidence({ c, all, onClose, onCite, ask }: { c: Citation; all: Citation[]; onClose: () => void; onCite: (n: number) => void; ask: (q: string) => void }) {
  useEffect(() => {
    const f = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  }, [onClose]);
  const kindLabel = { filing: "Company disclosure", computed: "Calculation", note: "Note" }[c.kind];
  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label="Source">
        <div className="drawer-h">
          <div>
            <div className="drawer-k">{kindLabel}</div>
            <div className="drawer-t">{c.kind === "filing" ? c.company : c.label}</div>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><I.x /></button>
        </div>
        <div className="drawer-b">
          {c.kind === "filing" && (
            <>
              <div className="addr two">
                <div><div className="addr-k">Document</div><div className="addr-v">BRSR filing</div></div>
                <div><div className="addr-k">Financial year</div><div className="addr-v">{c.fy}</div></div>
              </div>
              <div>
                <div className="card-t" style={{ fontSize: 14 }}>{c.item}</div>
                <div className="card-s" style={{ marginTop: 4 }}>{c.where}</div>
              </div>
              {c.text ? <div className="fulltext">{c.text}</div> : <div className="valuebox"><div className="card-s">As disclosed by the company</div><div className="v tnum">{c.value}</div></div>}
              <div><button className="btn" onClick={() => { onClose(); ask(`Tell me about ${c.company}`); }}><I.building />More about this company</button></div>
            </>
          )}
          {c.kind === "computed" && (
            <>
              <div className="valuebox"><div className="card-s">How it is calculated</div><div style={{ fontSize: 14.5, marginTop: 6, overflowWrap: "anywhere" }} className="tnum">{c.formula}</div></div>
              {c.note && <div className="card-s" style={{ fontSize: 13 }}>{c.note}</div>}
              {c.inputs?.length > 0 && (
                <div>
                  <div className="card-s" style={{ marginBottom: 8 }}>Figures used</div>
                  {c.inputs.map((ref: string) => {
                    const n = Number(ref.replace(/\D/g, ""));
                    const src = all.find((x) => x.id === n);
                    return src ? (
                      <button key={ref} className="src" onClick={() => onCite(n)}>
                        <span className="src-what">{citeWhat(src)}</span><span className="src-val tnum">{srcValue(src)}</span><span className="src-where">{citeWhere(src)}</span>
                      </button>
                    ) : null;
                  })}
                </div>
              )}
              <div className="card-s">Calculated from figures the companies disclosed. Nothing is estimated.</div>
            </>
          )}
          {c.kind === "note" && <div className="fulltext" style={{ borderLeftColor: "var(--accent)" }}>{c.text}</div>}
        </div>
      </aside>
    </>
  );
}

/* ---------------------------------------------------------------- answer */
function readVote(fp: string): number {
  try { return Number(localStorage.getItem("pramana.vote." + fp) || 0); } catch { return 0; }
}

function Followups({ items, ask }: { items: string[]; ask: (q: string) => void }) {
  const hover = useHoverPrefetch();
  return (
    <div className="followups">
      {items.map((f) => <button key={f} className="fu" onClick={() => ask(f)} {...hover(f)}><I.corner />{f}</button>)}
    </div>
  );
}

const NOTE_LABEL: Record<string, string> = { data: "Note", scope: "Not covered", method: "Note", context: "Note" };

export function AnswerView({ a, q, ctx, ask, index, prefetch, pickCompany }: {
  a: Answer; q: string; ctx?: Ctx; ask: (q: string) => void; index: number; prefetch?: (q: string) => void; pickCompany?: () => void;
}) {
  const [cite, setCite] = useState<number | null>(null);
  const [vote, setVote] = useState<number>(() => readVote(a.fingerprint));
  const [noteOpen, setNoteOpen] = useState(false);
  const [note, setNote] = useState("");
  const rate = (r: 1 | -1) => {
    setVote(r);
    try { localStorage.setItem("pramana.vote." + a.fingerprint, String(r)); } catch { /* storage unavailable */ }
    if (r === 1) { sendFeedback(a, q, 1).catch(() => {}); toast("Thank you for the feedback."); setNoteOpen(false); }
    else setNoteOpen(true);
  };
  const submitNote = () => {
    sendFeedback(a, q, -1, note).catch(() => {});
    setNoteOpen(false);
    toast("Thank you. Your feedback has been recorded.");
  };
  const c = a.citations.find((x) => x.id === cite) || null;

  const share = async () => {
    const short = await createShare(q, ctx, a.fingerprint);
    let link = short;
    if (!link) {
      const u = new URL(window.location.origin);
      u.searchParams.set("q", q);
      const c2 = { ...(ctx || {}) };
      if (c2.companies?.length || c2.intent || c2.prefs || c2.lens) u.searchParams.set("ctx", btoa(unescape(encodeURIComponent(JSON.stringify(c2)))));
      link = u.toString();
    }
    navigator.clipboard?.writeText(link).then(() => toast("Link copied"));
  };
  const copy = () => {
    const pts = a.blocks.filter((b) => b.type === "points").flatMap((b) => b.items.map((t: string) => "• " + t));
    const clean = (p: string) => p.replace(/\*\*/g, "").replace(/\s*\[\d+\]/g, "");
    const src = a.citations.filter((x) => x.kind === "filing").map((x) => `${x.company}, BRSR ${x.fy}: ${x.item}`);
    const txt = `${a.title}\n\n${[...a.lead, ...pts].map(clean).join("\n\n")}${src.length ? `\n\nSources\n${[...new Set(src)].join("\n")}` : ""}`;
    navigator.clipboard?.writeText(txt).then(() => toast("Answer copied"));
  };
  const print = () => {
    const el = document.getElementById(`ans-${index}`);
    if (!el) return;
    // Lay the answer out at page width first, so charts are measured for paper and not for the screen.
    document.body.classList.add("print-one");
    el.classList.add("print-target");
    document.querySelectorAll(".print-q").forEach((n) => n.classList.remove("print-q"));
    el.previousElementSibling?.classList.add("print-q");
    const src = el.querySelector("details.sources") as HTMLDetailsElement | null;
    const wasOpen = src?.open ?? false;
    if (src) src.open = true;
    // supporting detail that is folded away on screen is part of the printed answer
    const more = Array.from(el.querySelectorAll("details.more")) as HTMLDetailsElement[];
    const moreOpen = more.map((d) => d.open);
    more.forEach((d) => (d.open = true));
    const done = () => {
      document.body.classList.remove("print-one");
      el.classList.remove("print-target");
      if (src) src.open = wasOpen;
      more.forEach((d, i) => (d.open = moreOpen[i]));
      window.removeEventListener("afterprint", done);
    };
    window.addEventListener("afterprint", done);
    setTimeout(() => window.print(), 320);
  };
  const sources = a.citations.filter((x) => x.kind !== "note");   // explanations are part of the answer, not sources
  const filings = sources.filter((x) => x.kind === "filing").length;
  const hasData = a.citations.length > 0 || a.blocks.some((b) => b.export);

  return (
    <AnswerCtx.Provider value={{ citations: a.citations, openCite: setCite, activeCite: cite, ask, prefetch, pickCompany }}>
      <article className="answer" id={`ans-${index}`}>
        {a.kicker && <div className="ans-kicker">{a.kicker}</div>}
        <h2 className="ans-title">{a.title}</h2>
        <div className="lead">{a.lead.map((p, i) => <p key={i}><Rich text={p} /></p>)}</div>
        {a.blocks.length > 0 && <div className="blocks">{a.blocks.map((b, i) => <BlockView key={i} b={b} i={i} />)}</div>}
        {a.notes.length > 0 && (
          <div className="notes">
            {a.notes.map((n, i) => (
              <div key={i} className={"note " + n.kind}>
                <I.info />
                <div><span className="note-k">{NOTE_LABEL[n.kind] || "Note"}</span>{n.text}</div>
              </div>
            ))}
          </div>
        )}
        {a.followups.length > 0 && <Followups items={a.followups} ask={ask} />}
        {sources.length > 0 && (
          <details className="sources">
            <summary>
              <span><b style={{ color: "var(--ink)" }}>Sources</b>{filings > 0 ? " · company BRSR filings" : " · how this was calculated"}</span>
              <I.down style={{ width: 14, height: 14 }} />
            </summary>
            <div className="src-list">
              {sources.map((x) => (
                <button key={x.id} className="src" onClick={() => setCite(x.id)}>
                  <span className="src-what">{citeWhat(x)}</span><span className="src-val tnum">{srcValue(x)}</span><span className="src-where">{citeWhere(x)}</span>
                </button>
              ))}
            </div>
          </details>
        )}
        <div className="foot-row">
          <span className="fb">
            <button className={"tool icon" + (vote === 1 ? " on-up" : "")} onClick={() => rate(1)} aria-label="Helpful" title="Helpful"><I.thumb /></button>
            <button className={"tool icon" + (vote === -1 ? " on-down" : "")} onClick={() => rate(-1)} aria-label="Not helpful" title="Not helpful"><I.thumb style={{ transform: "rotate(180deg)" }} /></button>
            <button className="tool icon" onClick={copy} title="Copy answer" aria-label="Copy answer"><I.copy /></button>
            <button className="tool icon" onClick={share} title="Copy link to this answer" aria-label="Copy link"><I.link /></button>
          </span>
          <span className="ans-actions">
            {hasData && <button className="tool" onClick={() => downloadAnswer(a, q)} title="Download this answer as an Excel workbook"><I.download /> Excel</button>}
            <button className="tool" onClick={print} title="Save this answer as a PDF"><I.print /> PDF</button>
          </span>
        </div>
        {noteOpen && (
          <div className="fb-note">
            <input autoFocus placeholder="What were you expecting instead? (optional)" value={note} maxLength={400}
                   onChange={(e) => setNote(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submitNote()} />
            <button className="btn" onClick={submitNote}>Send</button>
          </div>
        )}
      </article>
      {c && <Evidence c={c} all={a.citations} onClose={() => setCite(null)} onCite={setCite} ask={ask} />}
    </AnswerCtx.Provider>
  );
}
