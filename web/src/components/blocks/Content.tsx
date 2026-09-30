import { useMemo, useState, type ReactNode } from "react";
import { I } from "../../icons";
import { CiteChip, Rich, useAnswer, useCountUp, useHoverPrefetch } from "../../ui";
import { heat } from "./Charts";

/* =============================================================== KPIs */
function KpiTile({ k, i }: { k: any; i: number }) {
  const v = useCountUp(String(k.value));
  const tone = k.big ? (k.tone === "good" ? " tone-good" : k.tone === "bad" ? " tone-bad" : "") : "";
  return (
    <div className={"kpi" + (k.big ? " big" : "") + tone} style={{ animation: `rise .5s ${i * 60}ms both` }}>
      <div className="kpi-l"><span>{k.label}</span>{k.cite && <CiteChip refText={k.cite} />}</div>
      <div className="kpi-v">{v}</div>
      {k.sub && <div className="kpi-s">{k.sub}</div>}
      {k.delta && k.delta.text && (
        <span className={"delta " + (k.delta.tone || "")}>
          {k.delta.tone === "good" ? <I.down /> : k.delta.tone === "bad" ? <I.up /> : null}
          {k.delta.text}
        </span>
      )}
    </div>
  );
}
export function Kpis({ b }: { b: any }) {
  return <div className="kpis">{b.items.map((k: any, i: number) => <KpiTile k={k} i={i} key={i} />)}</div>;
}

/* =============================================================== Rubric */
export function Rubric({ b }: { b: any }) {
  const dist = b.distribution || null;
  const total = dist ? Object.entries(dist).reduce((a, [k, v]: any) => (k === "none" ? a : a + v), 0) : 0;
  return (
    <div>
      <div className="rubric">
        {b.levels.map((l: any) => {
          const n = dist ? dist[String(l.score)] ?? 0 : null;
          return (
            <div key={l.score} className={"rub" + (b.score === l.score ? " on" : "")} title={l.raw || ""}>
              <span className="rub-s">{l.score}</span>
              <span>{l.text}</span>
              {n != null ? (
                <span style={{ textAlign: "right" }}>
                  <span className="rub-n">{n} {n === 1 ? "company" : "companies"}</span>
                  <div className="rub-meter"><i style={{ width: `${total ? (100 * n) / total : 0}%` }} /></div>
                </span>
              ) : <span />}
            </div>
          );
        })}
      </div>
      <div className="legend">
        {b.score != null && <span><i style={{ background: "var(--focus)" }} />Score {b.score}</span>}
        {b.distribution_label && <span className="muted">Counts: {b.distribution_label}{dist?.none ? `, ${dist.none} without a score` : ""}</span>}
        {b.source && <span className="muted">Scale: {b.source}</span>}
        {b.zero_note && <span className="muted">{b.zero_note}</span>}
      </div>
    </div>
  );
}

/* =============================================================== Checklist */
export function Checklist({ b }: { b: any }) {
  return (
    <div className="checks">
      {b.items.map((it: any, i: number) => {
        const cls = it.value == null ? "u" : it.value ? "y" : "n";
        return (
          <div key={i} className={"check " + cls} style={{ animation: `rise .4s ${i * 30}ms both` }}>
            <span className="ic">{it.value == null ? <I.minus /> : it.value ? <I.check /> : <I.x />}</span>
            <span className="t">{it.label}</span>
            <CiteChip refText={it.cite} />
          </div>
        );
      })}
    </div>
  );
}

/* =============================================================== Quotes */
function Highlighted({ text, segments, excerpt }: { text: string; segments: any[]; excerpt?: boolean }) {
  const parts: ReactNode[] = [];
  const segs = [...(segments || [])].sort((a, b) => a.start - b.start);
  const renderSeg = (s: any, key: string) => {
    const body = text.slice(s.start, s.end);
    const marks: number[][] = (s.marks || []).map((m: number[]) => [m[0] - s.start, m[1] - s.start]).sort((a: number[], b: number[]) => a[0] - b[0]);
    const inner: ReactNode[] = [];
    let pos = 0;
    marks.forEach((m, j) => {
      if (m[0] > pos) inner.push(body.slice(pos, m[0]));
      inner.push(<mark key={j}>{body.slice(m[0], m[1])}</mark>);
      pos = m[1];
    });
    inner.push(body.slice(pos));
    return <span key={key} className={s.highlight ? "hl" : "plain"}>{inner}</span>;
  };
  if (excerpt) {
    segs.forEach((s, i) => {
      if (s.start > 0) parts.push(<span key={"e" + i}>{"… "}</span>);
      parts.push(renderSeg(s, "s" + i));
      if (s.end < text.length) parts.push(<span key={"f" + i}>{" …"}</span>);
    });
    return <>{parts}</>;
  }
  let pos = 0;
  segs.forEach((s, i) => {
    if (s.start > pos) parts.push(<span key={"g" + i}>{text.slice(pos, s.start)}</span>);
    parts.push(renderSeg(s, "s" + i));
    pos = s.end;
  });
  if (pos < text.length) parts.push(<span key="tail">{text.slice(pos)}</span>);
  return <>{parts}</>;
}

function QuoteCard({ it, excerpt, i }: { it: any; excerpt?: boolean; i: number }) {
  const [open, setOpen] = useState(false);
  const { ask } = useAnswer();
  const long = (it.text || "").length > 700;
  const showExcerpt = excerpt && !open;
  return (
    <article className="quote" style={{ animation: `rise .5s ${i * 80}ms both` }}>
      <div className="quote-h">
        <div>
          <div className="quote-co"><button className="linkish" style={{ color: "var(--ink)" }} onClick={() => ask(`Show ${it.short}'s E1 profile`)}>{it.short || it.company}</button></div>
          <div className="quote-meta">{it.sector} · Q{it.qid} {it.question}{it.mentions ? ` · ${it.mentions} mention${it.mentions > 1 ? "s" : ""}` : ""}</div>
        </div>
        {it.score != null && <span className={"score-badge s" + it.score}>{it.score}/100</span>}
      </div>
      <div className={"qtext" + (!showExcerpt && long && !open ? " clamped" : "")}>
        <Highlighted text={it.text} segments={it.segments} excerpt={showExcerpt} />
      </div>
      {it.themes?.length > 0 && <div className="themes">{it.themes.map((t: string) => <span className="theme" key={t}>{t}</span>)}</div>}
      <div className="quote-foot">
        <span>Base Data · {it.cell} <CiteChip refText={it.cite} /> {it.rating_cite && <CiteChip refText={it.rating_cite} />}</span>
        {(long || excerpt) && <button className="linkish" onClick={() => setOpen(!open)}>{open ? "Show less" : excerpt ? "Show full disclosure" : "Show full text"}</button>}
      </div>
    </article>
  );
}

export function Quotes({ b }: { b: any }) {
  return (
    <div className={"quotes" + (b.columns ? " cols" : "")}>
      {b.items.map((it: any, i: number) => <QuoteCard key={it.company_id + it.qid} it={it} excerpt={b.excerpt} i={i} />)}
    </div>
  );
}

export function ReportQuotes({ b }: { b: any }) {
  return (
    <div className="rqs">
      {b.items.map((it: any, i: number) => (
        <blockquote className="rq" key={i} style={{ animation: `rise .5s ${i * 70}ms both` }}>
          <p>{it.text}</p>
          <footer>
            <span>{it.where}</span>
            {it.pdf_page && <a href={`/files/report.pdf#page=${it.pdf_page}`} target="_blank" rel="noreferrer">PDF page {it.pdf_page} <I.ext style={{ width: 11, height: 11, verticalAlign: -1 }} /></a>}
            <CiteChip refText={it.cite} />
          </footer>
        </blockquote>
      ))}
    </div>
  );
}

/* =============================================================== Insights */
function signalTone(s: string) {
  if (/strong|improving/i.test(s)) return "good";
  if (/critical|weak|concerning/i.test(s)) return "bad";
  return "warn";
}
export function Insights({ b }: { b: any }) {
  return (
    <div className="insights">
      {b.items.map((it: any, i: number) => {
        const t = signalTone(it.signal);
        return (
          <div className="ins" key={i} style={{ animation: `rise .45s ${i * 50}ms both` }}>
            <div><span className={"signal " + t}>{t === "good" ? <I.check /> : t === "bad" ? <I.alert /> : <I.info />}{it.signal}</span></div>
            <div>
              <div className="ins-a">{it.area}</div>
              <div className="ins-o">{it.observation} <CiteChip refText={it.cite} /></div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* =============================================================== Table */
export function Table({ b }: { b: any }) {
  const { ask } = useAnswer();
  const [sort, setSort] = useState<{ k: string; d: 1 | -1 } | null>(null);
  const rows = useMemo(() => {
    if (!sort) return b.rows;
    const parse = (v: any) => {
      if (typeof v === "number") return v;
      const s = String(v ?? "").replace(/[,%−+]/g, (m) => (m === "−" ? "-" : "")).replace(/[KMB]$/, "");
      const n = parseFloat(s);
      const mult = /K$/.test(String(v)) ? 1e3 : /M$/.test(String(v)) ? 1e6 : /B$/.test(String(v)) ? 1e9 : 1;
      return isNaN(n) ? String(v ?? "") : n * mult;
    };
    return [...b.rows].sort((x: any, y: any) => {
      const a = parse(x[sort.k]), c = parse(y[sort.k]);
      if (typeof a === "number" && typeof c === "number") return (a - c) * sort.d;
      return String(a).localeCompare(String(c)) * sort.d;
    });
  }, [b.rows, sort]);
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            {b.columns.map((c: any) => (
              <th key={c.key} className={c.align === "right" ? "r" : ""} onClick={() => setSort(sort && sort.k === c.key ? { k: c.key, d: (sort.d * -1) as 1 | -1 } : { k: c.key, d: 1 })}>
                {c.label}{sort && sort.k === c.key ? (sort.d === 1 ? " ↑" : " ↓") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r: any, i: number) => (
            <tr key={i} className={r.highlight ? "hi" : ""}>
              {b.columns.map((c: any) => {
                const v = r[c.key];
                const cls = (c.align === "right" ? "r " : "") + (c.key === "company" ? "co" : "");
                if (c.key === "company" && r.id) return <td key={c.key} className={cls}><button className="colink" onClick={() => ask(`Show ${v}'s E1 profile`)}>{v}</button>{r.cite && <> <CiteChip refText={r.cite} /></>}</td>;
                const yn = v === "Yes" ? "yes" : v === "No" || v === "No / NA" ? "no" : "";
                return <td key={c.key} className={cls + " " + yn}>{v}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function tableCsv(b: any): string {
  const esc = (s: any) => `"${String(s ?? "").replace(/"/g, '""')}"`;
  return [b.columns.map((c: any) => esc(c.label)).join(","), ...b.rows.map((r: any) => b.columns.map((c: any) => esc(r[c.key])).join(","))].join("\n");
}

/* =============================================================== Compare scorecard */
export function Compare({ b }: { b: any }) {
  const { ask } = useAnswer();
  return (
    <div className="tbl-wrap" style={{ maxHeight: "none" }}>
      <table className="cmp">
        <thead>
          <tr>
            <th />
            {b.columns.map((c: any) => <th key={c.id}><button className="colink" style={{ fontWeight: 600 }} onClick={() => ask(`Show ${c.label}'s E1 profile`)}>{c.label}</button><small>{c.sub}</small></th>)}
          </tr>
        </thead>
        <tbody>
          {b.rows.map((r: any, i: number) => (
            <tr key={i}>
              <td>{r.label}</td>
              {r.cells.map((c: any, j: number) => (
                <td key={j} className={(c.best ? "best " : "") + (c.tone || "")} title={c.full || ""}>
                  {c.score !== undefined && c.score !== null ? <span className="heat" style={heat(c.score)}>{c.text}</span> : c.text}
                  {c.cite && <> <CiteChip refText={c.cite} /></>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Matrix({ b }: { b: any }) {
  return (
    <div className="tbl-wrap" style={{ maxHeight: "none" }}>
      <table className="tbl matrix">
        <thead><tr><th>Practice</th>{b.columns.map((c: string) => <th key={c} style={{ textAlign: "center" }}>{c}</th>)}</tr></thead>
        <tbody>
          {b.rows.map((r: any) => (
            <tr key={r.label}><td>{r.label}</td>{r.values.map((v: boolean, i: number) => <td key={i} className={v ? "y" : "n"}>{v ? "●" : "·"}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Gap({ b }: { b: any }) {
  return (
    <div className="gap">
      <div className="gap-col">
        <h5>Named in {b.company}'s disclosure</h5>
        {b.my_themes.length ? <div className="themes" style={{ marginTop: 0 }}>{b.my_themes.map((t: string) => <span className="theme" key={t}>{t}</span>)}</div> : <span className="muted" style={{ fontSize: 13 }}>No recognised practice families.</span>}
        <div className="card-s" style={{ marginTop: 12 }}>Score {b.score ?? "n/a"}/100 · specificity {b.my_specificity?.toFixed?.(1) ?? "n/a"}</div>
      </div>
      <div className="gap-col" style={{ borderColor: "color-mix(in oklab, var(--focus) 40%, var(--line))" }}>
        <h5>Common among top-rated peers, not named</h5>
        {b.missing.length ? <div className="themes" style={{ marginTop: 0 }}>{b.missing.map((t: string) => <span className="theme" key={t} style={{ borderColor: "var(--focus)", color: "var(--ink)" }}>{t}</span>)}</div> : <span className="muted" style={{ fontSize: 13 }}>None of the common practice families are missing.</span>}
        <div className="card-s" style={{ marginTop: 12 }}>Leaders' median specificity {b.leader_specificity?.toFixed?.(1) ?? "n/a"}</div>
      </div>
    </div>
  );
}

export function Choices({ b }: { b: any }) {
  const { ask } = useAnswer();
  const hover = useHoverPrefetch();
  return (
    <div className="choices">
      {b.items.map((o: any) => (
        <button className="choice" key={o.id} onClick={() => ask(o.query)} {...hover(o.query)}>
          <span><b style={{ fontWeight: 600 }}>{o.name}</b><div className="card-s">{o.sector}</div></span>
          <I.arrow style={{ width: 16, height: 16, color: "var(--ink-3)" }} />
        </button>
      ))}
    </div>
  );
}

export function Capabilities({ b }: { b: any }) {
  const { ask } = useAnswer();
  const hover = useHoverPrefetch();
  return (
    <div className="caps">
      {b.items.map((c: any) => (
        <button className="cap" key={c.title} onClick={() => ask(c.example)} {...hover(c.example)}>
          <b>{c.title}</b><span>{c.text}</span><em>{"“"}{c.example}{"”"}</em>
        </button>
      ))}
    </div>
  );
}

export function Links({ b }: { b: any }) {
  return <div className="links">{b.items.map((u: string) => <a key={u} href={u} target="_blank" rel="noreferrer noopener">{u}</a>)}</div>;
}

export function Callout({ b }: { b: any }) {
  return <div className={"callout " + (b.tone || "")}><b>{b.title}</b><span style={{ fontSize: 14, color: "var(--ink-2)" }}><Rich text={b.text} /></span></div>;
}
