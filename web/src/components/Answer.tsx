import { Fragment, useEffect, useState } from "react";
import type { Answer, Citation, Ctx } from "../api";
import { I } from "../icons";
import { AnswerCtx, Rich, toast } from "../ui";
import { BlockView } from "./blocks";
import { Rubric } from "./blocks/Content";

export function citeWhere(c: Citation): string {
  switch (c.kind) {
    case "cell": return `Base Data!${c.cell}`;
    case "rating": return `Rating!${c.cell}`;
    case "report_table": return `Table ${c.table} · p.${c.pdf_page}`;
    case "report_text": return c.pdf_page ? `Report · p.${c.pdf_page}` : "Report";
    case "derived": return "Computed";
    default: return "Method note";
  }
}
export function citeWhat(c: Citation): string {
  switch (c.kind) {
    case "cell": return `${c.company}: ${c.question}`;
    case "rating": return `${c.company}: rating ${c.score ?? "n/a"} on Q${c.qid}`;
    case "report_table": return `Table ${c.table}: ${c.title}${c.row ? ` (${c.row})` : ""}`;
    case "report_text": return `“${String(c.text).slice(0, 110)}${String(c.text).length > 110 ? "…" : ""}”`;
    case "derived": return c.label;
    default: return c.label;
  }
}

/* ---------------------------------------------------------------- evidence drawer */
export function Evidence({ c, all, onClose, onCite, ask }: { c: Citation; all: Citation[]; onClose: () => void; onCite: (n: number) => void; ask: (q: string) => void }) {
  useEffect(() => {
    const f = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  }, [onClose]);
  const kindLabel = { cell: "Workbook cell", rating: "Rating score", report_table: "Report table", report_text: "Report text", derived: "Computation", method: "Method note" }[c.kind];
  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label="Source">
        <div className="drawer-h">
          <div>
            <div className="drawer-k"><span className="cite on" style={{ cursor: "default" }}>{c.id}</span>{kindLabel}</div>
            <div className="drawer-t">{c.kind === "cell" || c.kind === "rating" ? c.company : c.kind === "report_table" ? `Table ${c.table}` : c.label || "IIMB report"}</div>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><I.x /></button>
        </div>
        <div className="drawer-b">
          {c.kind === "cell" && (
            <>
              <div className="addr">
                <div><div className="addr-k">File</div><div className="addr-v">E1 data.xlsx</div></div>
                <div><div className="addr-k">Sheet</div><div className="addr-v">{c.sheet}</div></div>
                <div><div className="addr-k">Cell</div><div className="addr-v">{c.cell}</div></div>
              </div>
              <div>
                <div className="card-s">Q{c.qid} · {c.question}</div>
                {c.brsr && <div className="card-s mono" style={{ marginTop: 6, fontSize: 11.5 }}>{c.brsr}</div>}
              </div>
              {c.text ? <div className="fulltext">{c.text}</div> : <div className="valuebox"><div className="card-s">Value as filed</div><div className="v tnum">{c.value}</div></div>}
              <div><button className="btn" onClick={() => { onClose(); ask(`Show ${c.company}'s E1 profile`); }}><I.building />Open company profile</button></div>
            </>
          )}
          {c.kind === "rating" && (
            <>
              <div className="addr">
                <div><div className="addr-k">Sheet</div><div className="addr-v">Rating</div></div>
                <div><div className="addr-k">Cell</div><div className="addr-v">{c.cell || "n/a"}</div></div>
                <div><div className="addr-k">Question</div><div className="addr-v">Q{c.qid}</div></div>
              </div>
              <div className="valuebox"><div className="card-s">{c.question}</div><div className="v">{c.score == null ? "No score" : `${c.score} / 100`}</div></div>
              {c.rubric?.length > 0 && <Rubric b={{ levels: c.rubric.map((l: any) => ({ score: l.score, text: l.text })), score: c.score, source: c.rule_source }} />}
            </>
          )}
          {c.kind === "report_table" && (
            <>
              <div className="card-s">{c.title}</div>
              {(() => {
                const clean = (h: string) => h.replace(/\s+/g, " ").trim();
                const hit = c.row ? c.rows.find((r: string[]) => r[0] === c.row) : null;
                return hit ? (
                  <div className="rowcard">
                    <div className="rowcard-h">Cited row: {clean(hit[0])}</div>
                    <dl>{c.columns.slice(1).map((h: string, j: number) => <Fragment key={j}><dt>{clean(h) || "Value"}</dt><dd>{hit[j + 1]}</dd></Fragment>)}</dl>
                  </div>
                ) : null;
              })()}
              <details open={!c.row}>
              <summary className="card-s" style={{ cursor: "pointer", margin: "4px 0 8px" }}>Full table as published</summary>
              <div className="tbl-wrap" style={{ maxHeight: 420 }}>
                <table className="mini-table">
                  <thead><tr>{c.columns.map((h: string, i: number) => <th key={i}>{h.replace(/\s+/g, " ").trim()}</th>)}</tr></thead>
                  <tbody>
                    {c.rows.map((r: string[], i: number) => (
                      <tr key={i} className={c.row && r[0] === c.row ? "hit" : ""}>{r.map((x, j) => <td key={j} className={j > 0 ? "num" : ""}>{x}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
              </details>
              {c.note && <div className="card-s">{c.note}</div>}
              <div><a className="btn" href={`/files/report.pdf#page=${c.pdf_page}`} target="_blank" rel="noreferrer"><I.book />Open report at PDF page {c.pdf_page} (printed {c.printed_page})</a></div>
            </>
          )}
          {c.kind === "report_text" && (
            <>
              <blockquote className="rq"><p>{c.text}</p><footer>{c.where}</footer></blockquote>
              {c.pdf_page && <div><a className="btn" href={`/files/report.pdf#page=${c.pdf_page}`} target="_blank" rel="noreferrer"><I.book />Open report at PDF page {c.pdf_page}</a></div>}
            </>
          )}
          {c.kind === "derived" && (
            <>
              <div className="valuebox"><div className="card-s">Formula</div><div className="mono" style={{ fontSize: 13.5, marginTop: 6, overflowWrap: "anywhere" }}>{c.formula}</div></div>
              {c.note && <div className="card-s" style={{ fontSize: 13 }}>{c.note}</div>}
              {c.inputs?.length > 0 && (
                <div>
                  <div className="card-s" style={{ marginBottom: 8 }}>Inputs</div>
                  {c.inputs.map((ref: string) => {
                    const n = Number(ref.replace(/\D/g, ""));
                    const src = all.find((x) => x.id === n);
                    return src ? (
                      <button key={ref} className="src" onClick={() => onCite(n)}>
                        <span className="src-n">[{n}]</span><span className="src-what">{citeWhat(src)}</span><span className="src-where">{citeWhere(src)}</span>
                      </button>
                    ) : null;
                  })}
                </div>
              )}
              <div className="card-s">Computed deterministically from the cited cells. No estimation or imputation.</div>
            </>
          )}
          {c.kind === "method" && <div className="fulltext" style={{ borderLeftColor: "var(--accent)" }}>{c.text}</div>}
        </div>
      </aside>
    </>
  );
}

/* ---------------------------------------------------------------- trace */
function Trace({ t }: { t: any }) {
  const ents = t.entities || {};
  return (
    <div className="trace">
      <h4>How this was understood and answered</h4>
      <div className="pipeline">
        <div className="stage"><div className="stage-k">1 Normalise</div><div className="stage-v">{(t.normalized || "").split(" ").map((w: string, i: number) => <span key={i} className={"tok" + (w.startsWith("<") ? " ent" : "")}>{w}</span>)}</div></div>
        <div className="stage">
          <div className="stage-k">2 Classify</div>
          <div className="stage-v">
            {(t.model?.top3 || []).map(([k, p]: [string, number]) => (
              <div className="prob" key={k}><span className="mono" style={{ fontSize: 11.5 }}>{k}</span><span className="prob-bar"><i style={{ width: `${p * 100}%` }} /></span><span className="mono tnum" style={{ fontSize: 11.5 }}>{(p * 100).toFixed(1)}%</span></div>
            ))}
          </div>
        </div>
        <div className="stage">
          <div className="stage-k">3 Link</div>
          <div className="stage-v" style={{ fontSize: 12.5 }}>
            {ents.companies?.map((c: any) => <div key={c.id}>Company: <b>{c.name}</b></div>)}
            {ents.sector && <div>Sector: <b>{ents.sector}</b></div>}
            {ents.metric && <div>Metric: <b>{ents.metric}</b></div>}
            {ents.tech?.length > 0 && <div>Search: <b>{ents.tech.join(", ")}</b></div>}
            {ents.offtopic?.length > 0 && <div>Out of scope: <b>{ents.offtopic.join(", ")}</b></div>}
            {ents.absent?.length > 0 && <div>Not in dataset: <b>{ents.absent.join(", ")}</b></div>}
            {!ents.companies?.length && !ents.sector && !ents.metric && <span className="muted">No entities</span>}
          </div>
        </div>
        <div className="stage">
          <div className="stage-k">4 Ground</div>
          <div className="stage-v" style={{ fontSize: 12.5 }}>
            <div>{t.grounding?.citations} citations</div>
            <div>{t.grounding?.numeric_paragraphs} numeric statements, {t.grounding?.uncited?.length ?? 0} uncited</div>
            <div className="muted">{t.timing_ms?.understand} ms + {t.timing_ms?.compose} ms</div>
          </div>
        </div>
      </div>
      <div className="card-s" style={{ marginBottom: 6 }}>Final route: <b className="mono">{t.final_intent}</b>{t.model && <> · model topic <span className="mono">{t.model.topic}</span> ({(t.model.topic_p * 100).toFixed(0)}%)</>}</div>
      {t.rules?.length > 0 && <div>{t.rules.map((r: string, i: number) => <div className="rule" key={i}>rule: {r}</div>)}</div>}
      {t.used_context && Object.keys(t.used_context).length > 0 && <div className="rule">memory: used {Object.keys(t.used_context).join(", ")} from earlier in this conversation</div>}
      <div className="card-s" style={{ marginTop: 8 }}>BPE pieces: <span className="mono" style={{ fontSize: 11.5 }}>{(t.model?.tokens || []).join(" ")}</span></div>
    </div>
  );
}

/* ---------------------------------------------------------------- answer */
export function AnswerView({ a, q, ctx, ask, index }: { a: Answer; q: string; ctx?: Ctx; ask: (q: string) => void; index: number }) {
  const [cite, setCite] = useState<number | null>(null);
  const [trace, setTrace] = useState(false);
  const c = a.citations.find((x) => x.id === cite) || null;
  const notes = [...a.notes].sort((x, y) => (x.kind === "data_quality" || x.kind === "scope" ? -1 : 0) - (y.kind === "data_quality" || y.kind === "scope" ? -1 : 0));

  const share = () => {
    const u = new URL(window.location.origin);
    u.searchParams.set("q", q);
    const c2 = { ...(ctx || {}) };
    if (c2.companies?.length || c2.intent) u.searchParams.set("ctx", btoa(unescape(encodeURIComponent(JSON.stringify(c2)))));
    navigator.clipboard?.writeText(u.toString()).then(() => toast("Link copied. It reproduces this exact answer."));
  };
  const copy = () => {
    const src = a.citations.map((c) => `[${c.id}] ${citeWhat(c)} (${citeWhere(c)})`).join("\n");
    const txt = `${a.title}\n\n${a.lead.map((p) => p.replace(/\*\*/g, "")).join("\n\n")}\n\nSources\n${src}\n\nAnswer ID ${a.fingerprint}`;
    navigator.clipboard?.writeText(txt).then(() => toast("Answer copied with its sources"));
  };
  const print = () => {
    const el = document.getElementById(`ans-${index}`);
    document.body.classList.add("print-one");
    el?.classList.add("print-target");
    setTimeout(() => {
      window.print();
      document.body.classList.remove("print-one");
      el?.classList.remove("print-target");
    }, 50);
  };

  return (
    <AnswerCtx.Provider value={{ citations: a.citations, openCite: setCite, activeCite: cite, ask }}>
      <article className="answer" id={`ans-${index}`}>
        <div className="ans-kicker"><span className={"status-dot " + a.status} />{a.kicker}</div>
        <h2 className="ans-title">{a.title}</h2>
        {notes.length > 0 && (
          <div className="notes">
            {notes.map((n, i) => (
              <div key={i} className={"note " + n.kind}>
                {n.kind === "data_quality" || n.kind === "scope" ? <I.alert /> : <I.info />}
                <div><span className="note-k">{{ data_quality: "Data quality", scope: "Scope", method: "Method", context: "Context" }[n.kind] || n.kind}</span>{n.text}</div>
              </div>
            ))}
          </div>
        )}
        <div className="lead">{a.lead.map((p, i) => <p key={i}><Rich text={p} /></p>)}</div>
        {a.blocks.length > 0 && <div className="blocks">{a.blocks.map((b, i) => <BlockView key={i} b={b} i={i} />)}</div>}
        {a.followups.length > 0 && (
          <div className="followups">
            {a.followups.map((f) => <button key={f} className="fu" onClick={() => ask(f)}><I.corner />{f}</button>)}
          </div>
        )}
        {a.citations.length > 0 && (
          <details className="sources">
            <summary><span><b style={{ color: "var(--ink)" }}>{a.citations.length} {a.citations.length === 1 ? "source" : "sources"}</b> · every figure above links to one of these</span><I.down style={{ width: 14, height: 14 }} /></summary>
            <div className="src-list">
              {a.citations.map((c) => (
                <button key={c.id} className="src" onClick={() => setCite(c.id)}>
                  <span className="src-n">[{c.id}]</span><span className="src-what">{citeWhat(c)}</span><span className="src-where">{citeWhere(c)}</span>
                </button>
              ))}
            </div>
          </details>
        )}
        <div className="foot-row">
          <span className="fingerprint" title="Hash of the answer content and dataset version. Identical questions give identical IDs.">
            <I.shield style={{ width: 14, height: 14, color: "var(--good-ink)" }} />Answer ID <b>{a.fingerprint}</b> · dataset {a.trace?.dataset}
          </span>
          <span className="ans-actions">
            <button className={"tool" + (trace ? " on" : "")} onClick={() => setTrace(!trace)}><I.eye style={{ width: 13, height: 13, verticalAlign: -2 }} /> How I understood this</button>
            <button className="tool" onClick={copy} title="Copy text with sources"><I.copy style={{ width: 13, height: 13, verticalAlign: -2 }} /></button>
            <button className="tool" onClick={share} title="Copy share link"><I.link style={{ width: 13, height: 13, verticalAlign: -2 }} /></button>
            <button className="tool" onClick={print} title="Print or save as PDF"><I.print style={{ width: 13, height: 13, verticalAlign: -2 }} /></button>
          </span>
        </div>
        {trace && a.trace && <Trace t={a.trace} />}
      </article>
      {c && <Evidence c={c} all={a.citations} onClose={() => setCite(null)} onCite={setCite} ask={ask} />}
    </AnswerCtx.Provider>
  );
}
