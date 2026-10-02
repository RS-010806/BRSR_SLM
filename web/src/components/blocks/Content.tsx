import { useMemo, useState, type ReactNode } from "react";
import { I } from "../../icons";
import { CiteChip, Rich, useAnswer, useCountUp, useHoverPrefetch } from "../../ui";

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

/* =============================================================== Checklist */
export function Checklist({ b }: { b: any }) {
  return (
    <div className="checks">
      {b.items.map((it: any, i: number) => {
        const cls = it.value == null ? "u" : it.value ? "y" : "n";
        return (
          <div key={i} className={"check " + cls} style={{ animation: `rise .4s ${i * 30}ms both` }}>
            <span className="ic">{it.value == null ? <I.minus /> : it.value ? <I.check /> : <I.x />}</span>
            <span className="t">{it.label}{it.sub && <small>{it.sub}</small>}</span>
            <CiteChip refText={it.cite} />
          </div>
        );
      })}
    </div>
  );
}

/* =============================================================== Points */
export function Points({ b }: { b: any }) {
  return (
    <section className="points-wrap">
      {b.title && <h3 className="points-h">{b.title}</h3>}
      <ul className="points">
        {b.items.map((t: string, i: number) => (
          <li key={i} style={{ animation: `rise .4s ${i * 40}ms both` }}>
            <Rich text={t} />
            {b.examples?.[i] && <span className="eg"><b>{b.examples[i].who}:</b> {"“"}{b.examples[i].text}{"”"}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}

/* =============================================================== Names (the peers, by name) */
const initials = (name: string) => {
  const w = name.replace(/[^A-Za-z0-9 ]/g, " ").split(/\s+/).filter(Boolean);
  return ((w[0]?.[0] || "") + (w[1]?.[0] || w[0]?.[1] || "")).toUpperCase();
};
export function Names({ b }: { b: any }) {
  const { ask } = useAnswer();
  const hover = useHoverPrefetch();
  return (
    <div className="names">
      {b.items.map((it: any, i: number) => {
        const q = `Tell me about ${it.name}`;
        return (
          <button key={it.id} className="name" onClick={() => ask(q)} {...hover(q)} style={{ animation: `rise .4s ${Math.min(i, 24) * 18}ms both` }}>
            <span className="name-av" aria-hidden>{initials(it.name)}</span>
            <span className="name-t">{it.name}</span>
            <I.arrow />
          </button>
        );
      })}
    </div>
  );
}

/* =============================================================== Action */
export function Action({ b }: { b: any }) {
  const { pickCompany } = useAnswer();
  if (b.action !== "set_company") return null;
  return <div><button className="btn primary" onClick={() => pickCompany?.()}><I.building />{b.label}</button></div>;
}

/* =============================================================== Quotes (text exactly as the company disclosed it) */
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
  const long = (it.text || "").length > 520;
  const showExcerpt = excerpt && !open;
  return (
    <article className="quote" style={{ animation: `rise .5s ${i * 80}ms both` }}>
      <div className="quote-h">
        <div>
          <div className="quote-co"><button className="linkish" style={{ color: "var(--ink)" }} onClick={() => ask(`Tell me about ${it.short}`)}>{it.short || it.company}</button></div>
          <div className="quote-meta">{it.sector} · {it.topic}{it.mentions ? ` · ${it.mentions} mention${it.mentions > 1 ? "s" : ""}` : ""}</div>
        </div>
      </div>
      <div className={"qtext" + (!showExcerpt && long && !open ? " clamped" : "")}>
        <Highlighted text={it.text} segments={it.segments} excerpt={showExcerpt} />
      </div>
      {it.themes?.length > 0 && <div className="themes">{it.themes.map((t: string) => <span className="theme" key={t}>{t}</span>)}</div>}
      <div className="quote-foot">
        <span>As disclosed, FY 2024-25 <CiteChip refText={it.cite} /></span>
        {(long || excerpt) && <button className="linkish" onClick={() => setOpen(!open)}>{open ? "Show less" : excerpt ? "Show full disclosure" : "Show full text"}</button>}
      </div>
    </article>
  );
}

export function Quotes({ b }: { b: any }) {
  const body = (
    <div className={"quotes" + (b.columns ? " cols" : "")}>
      {b.items.map((it: any, i: number) => <QuoteCard key={it.key || it.company_id + i} it={it} excerpt={b.excerpt} i={i} />)}
    </div>
  );
  if (!b.collapsed) return body;
  /* supporting detail: closed by default so the answer stays short, one click to read the source text */
  return (
    <details className="more">
      <summary><I.arrow />{b.summary || "View the full disclosures"}</summary>
      {body}
    </details>
  );
}

/* =============================================================== Table */
const PAGE = 60;
export function Table({ b }: { b: any }) {
  const { ask } = useAnswer();
  const [sort, setSort] = useState<{ k: string; d: 1 | -1 } | null>(null);
  const [limit, setLimit] = useState(PAGE);
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
    <>
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
            {rows.slice(0, limit).map((r: any, i: number) => (
              <tr key={i} className={r.highlight ? "hi" : ""}>
                {b.columns.map((c: any) => {
                  const v = r[c.key];
                  const cls = (c.align === "right" ? "r " : "") + (c.key === "company" ? "co" : "");
                  if (c.key === "company" && r.id) return <td key={c.key} className={cls}><button className="colink" onClick={() => ask(`Tell me about ${v}`)}>{v}</button>{r.cite && <> <CiteChip refText={r.cite} /></>}</td>;
                  const yn = v === "Yes" ? "yes" : v === "No" ? "no" : "";
                  return <td key={c.key} className={cls + " " + yn}>{v}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > limit && (
        <div style={{ textAlign: "center", marginTop: 10 }}>
          <button className="btn" onClick={() => setLimit(limit + 200)}>Show more ({rows.length - limit} more)</button>
        </div>
      )}
    </>
  );
}

/* =============================================================== Side by side */
export function Compare({ b }: { b: any }) {
  const { ask } = useAnswer();
  return (
    <div className="tbl-wrap" style={{ maxHeight: "none" }}>
      <table className="cmp">
        <thead>
          <tr>
            <th />
            {b.columns.map((c: any) => <th key={c.id}><button className="colink" style={{ fontWeight: 600 }} onClick={() => ask(/^S\d+$/.test(c.id) ? `Give me an overview of the ${c.label} sector` : `Tell me about ${c.label}`)}>{c.label}</button><small>{c.sub}</small></th>)}
          </tr>
        </thead>
        <tbody>
          {b.rows.map((r: any, i: number) => (
            <tr key={i}>
              <td>{r.label}</td>
              {r.cells.map((c: any, j: number) => (
                <td key={j} className={c.tone || ""} title={c.full || ""}>
                  {c.text}
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
