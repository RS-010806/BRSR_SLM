import { useEffect, useMemo, useState } from "react";
import type { Meta } from "../api";
import { I } from "../icons";
import { compact } from "../ui";

const fmtPct = (v: number | null) => (v == null ? "n/a" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}%`);

/* ---------------------------------------------------------------- companies */
export function CompaniesPage({ onAsk, meta }: { onAsk: (q: string) => void; meta: Meta | null }) {
  const [rows, setRows] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [sector, setSector] = useState("");
  const [sort, setSort] = useState<{ k: string; d: number }>({ k: "index", d: -1 });
  const [limit, setLimit] = useState(100);
  useEffect(() => { fetch("/api/directory").then((r) => r.json()).then(setRows); }, []);
  const list = useMemo(() => {
    const s = q.toLowerCase();
    const f = rows.filter((r) => (!sector || r.sector === sector) && (!s || r.name.toLowerCase().includes(s)));
    const val = (r: any) => (sort.k === "s12" && !r.abs_ok ? null : r[sort.k]);
    return f.sort((a, b) => {
      const x = val(a), y = val(b);
      if (typeof x === "string" || typeof y === "string") return String(x).localeCompare(String(y)) * sort.d;
      if (x == null && y == null) return a.name.localeCompare(b.name);
      if (x == null) return 1;
      if (y == null) return -1;
      return (x - y) * sort.d || a.name.localeCompare(b.name);
    });
  }, [rows, q, sector, sort]);
  const th = (k: string, label: string, r = false) => (
    <th className={r ? "r" : ""} onClick={() => setSort(sort.k === k ? { k, d: -sort.d } : { k, d: k === "short" || k === "sector_name" ? 1 : -1 })}>
      {label}{sort.k === k ? (sort.d === 1 ? " ↑" : " ↓") : ""}
    </th>
  );
  return (
    <div className="page">
      <div className="page-h">
        <div>
          <div className="eyebrow">Explore</div>
          <h1>Companies</h1>
          <p>All {rows.length || 982} companies in the E1 dataset. Click a company to open its evidence-linked profile.</p>
        </div>
      </div>
      <div className="filters">
        <input className="input" placeholder="Filter by name" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="select" value={sector} onChange={(e) => setSector(e.target.value)}>
          <option value="">All sectors</option>
          {meta?.sectors.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.n})</option>)}
        </select>
      </div>
      <div className="tbl-wrap" style={{ maxHeight: "none", background: "var(--surface)" }}>
        <table className="tbl">
          <thead>
            <tr>
              {th("short", "Company")}{th("sector_name", "Sector")}{th("s12", "Scope 1+2 (tCO₂e)", true)}{th("s12_yoy", "YoY", true)}
              {th("intensity", "Intensity / ₹ cr", true)}{th("assured", "GHG assured")}{th("scope3", "Scope 3")}{th("targets", "Targets", true)}{th("index", "E1 index", true)}
            </tr>
          </thead>
          <tbody>
            {list.slice(0, limit).map((r) => (
              <tr key={r.id}>
                <td className="co"><button className="colink" onClick={() => onAsk(`Show ${r.short}'s E1 profile`)}>{r.short}</button>{r.flags.includes("magnitude_check") && <span title="Magnitude check flag" style={{ color: "var(--serious)", marginLeft: 6 }}>{"▲"}</span>}</td>
                <td>{r.sector_name}</td>
                <td className="r">{r.s12 == null ? <span className="muted">n/r</span> : compact(r.s12)}</td>
                <td className="r" style={{ color: r.s12_yoy == null ? undefined : r.s12_yoy < 0 ? "var(--good-ink)" : "var(--bad-ink)" }}>{fmtPct(r.s12_yoy)}</td>
                <td className="r">{r.intensity == null ? <span className="muted">n/a</span> : r.intensity.toLocaleString("en-US", { maximumFractionDigits: 1 })}</td>
                <td className={r.assured ? "yes" : "no"}>{r.assured ? "Yes" : "No"}</td>
                <td className={r.scope3 ? "yes" : "no"}>{r.scope3 ? "Yes" : "No"}</td>
                <td className="r">{r.targets ?? "n/a"}</td>
                <td className="r"><b style={{ fontWeight: 500 }}>{r.index == null ? "n/a" : r.index.toFixed(1)}</b></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {list.length > limit && <div style={{ textAlign: "center", marginTop: 14 }}><button className="btn" onClick={() => setLimit(limit + 200)}>Show more ({list.length - limit} remaining)</button></div>}
      <p className="muted" style={{ fontSize: 12.5, marginTop: 14 }}>
        {"▲"} marks a magnitude-check flag (Scope 1+2 below 0.1% of the sector median, likely filed in a scaled unit); such values are not ranked.
        The E1 index is derived by Pramana from Rating-sheet scores and is not an official IIMB score.
      </p>
    </div>
  );
}

/* ---------------------------------------------------------------- sectors */
export function SectorsPage({ onAsk }: { onAsk: (q: string) => void }) {
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => { fetch("/api/sectors").then((r) => r.json()).then(setRows); }, []);
  const max = Math.max(1, ...rows.map((r) => r.share));
  return (
    <div className="page">
      <div className="page-h">
        <div>
          <div className="eyebrow">Explore</div>
          <h1>Sectors</h1>
          <p>The 22 NSE sectors in the study, sorted by their share of disclosed Scope 1+2 emissions. Totals match Report Table 3.1.</p>
        </div>
        <button className="btn" onClick={() => onAsk("Which sector emits the most?")}><I.grid />Cross-sector view</button>
      </div>
      <div className="sector-grid">
        {[...rows].sort((a, b) => b.share - a.share).map((s, i) => (
          <button key={s.id} className="sector-card" onClick={() => onAsk(`Give me an overview of the ${s.name} sector`)} style={{ animation: `rise .45s ${i * 25}ms both` }}>
            <div className="sc-top"><span className="sc-name">{s.name}</span><span className="sc-code">{s.nse_code}</span></div>
            <div className="spark" title={`${s.share.toFixed(1)}% of disclosed Scope 1+2`}><i style={{ width: `${(100 * s.share) / max}%` }} /></div>
            <div className="sc-stats">
              <div className="sc-stat"><b>{compact(s.s12)}</b><span>tCO₂e, {s.share.toFixed(1)}%</span></div>
              <div className="sc-stat"><b style={{ color: s.yoy < 0 ? "var(--good-ink)" : "var(--bad-ink)" }}>{fmtPct(s.yoy)}</b><span>YoY</span></div>
              <div className="sc-stat"><b>{s.n}</b><span>companies</span></div>
            </div>
            <div className="sc-stats">
              <div className="sc-stat"><b>{Math.round((100 * s.assured) / s.n)}%</b><span>GHG assured</span></div>
              <div className="sc-stat"><b>{Math.round((100 * s.scope3) / s.n)}%</b><span>report Scope 3</span></div>
              <div className="sc-stat"><b>{s.median_intensity == null ? "n/a" : s.median_intensity.toFixed(1)}</b><span>median t/₹cr</span></div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- method */
export function MethodPage({ meta, onAsk }: { meta: Meta | null; onAsk: (q: string) => void }) {
  if (!meta) return <div className="page"><div className="skeleton" style={{ width: "40%", height: 30 }} /></div>;
  const r = meta.reconciliation;
  const m = meta.model;
  const e = meta.eval || {};
  const div = r.ai_scored_divergence || {};
  return (
    <div className="page">
      <div className="page-h">
        <div>
          <div className="eyebrow">Method and sources</div>
          <h1>How every answer is proved</h1>
          <p>Pramana is a small, purpose-built language system. It understands the question with a model trained from scratch, then answers only by computing over the provided data. Nothing is generated freely, so nothing can be invented.</p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 14 }}>
        <div className="card-h"><div><div className="card-t">Pipeline</div><div className="card-s">Same input, same output: there is no randomness at any stage</div></div></div>
        <div className="flow">
          {[
            ["01", "Normalise", "Unicode, possessives, Scope 1/2/3, fiscal years and numbers are canonicalised."],
            ["02", "Link", "A token trie resolves 2,664 company aliases, 22 sectors and 38 questions, with typo tolerance and known-absent names."],
            ["03", "Understand", `A ${m.layers}-layer transformer (${(m.params / 1000).toFixed(0)}K parameters, custom BPE) predicts intent and topic; rules override where text is explicit.`],
            ["04", "Compute", "Handlers compute values, ranks, medians and scenarios from the workbook, applying the report's own conventions."],
            ["05", "Prove", "Sentences are assembled from templates; every number carries a citation to a cell, rating, table or page."],
          ].map(([n, t, d]) => (
            <div className="flow-step" key={n}><div className="flow-n">{n}</div><div className="flow-t">{t}</div><div className="flow-d">{d}</div></div>
          ))}
        </div>
      </div>

      <div className="method-grid">
        <div className="card">
          <div className="card-t">Reconciliation with the IIMB report</div>
          <div className="card-s">Every table in the E1 chapter recomputed from the raw workbook</div>
          <div style={{ display: "flex", gap: 20, alignItems: "baseline", margin: "14px 0" }}>
            <div className="stat-big">{r.matched}/{r.total}</div><div className="muted">figures match exactly</div>
          </div>
          <div className="tbl-wrap" style={{ maxHeight: 260 }}>
            <table className="tbl"><thead><tr><th>Table</th><th className="r">Cells checked</th><th className="r">Matched</th></tr></thead>
              <tbody>{Object.entries(r.by_table).map(([t, v]) => <tr key={t}><td>Table {t}</td><td className="r">{v.checks}</td><td className="r yes">{v.matched}</td></tr>)}</tbody></table>
          </div>
        </div>
        <div className="card">
          <div className="card-t">Query-understanding model card</div>
          <div className="card-s">Trained from scratch on this domain; used only to classify, never to write</div>
          <table className="mini-table" style={{ marginTop: 12 }}>
            <tbody>
              <tr><td>Architecture</td><td className="num">Pre-LN transformer encoder, {m.layers} layers, {m.heads} heads, d={m.d_model}</td></tr>
              <tr><td>Parameters</td><td className="num">{m.params.toLocaleString()}</td></tr>
              <tr><td>Tokenizer</td><td className="num">Byte-pair encoding, {m.vocab_size} symbols</td></tr>
              <tr><td>Training data</td><td className="num">{m.train_examples.toLocaleString()} synthetic queries from a hand-written grammar</td></tr>
              <tr><td>Validation (synthetic)</td><td className="num">intent {(m.val_intent_acc * 100).toFixed(1)}%, topic {(m.val_topic_acc * 100).toFixed(1)}%</td></tr>
              <tr><td>Held-out hand-written queries</td><td className="num">{e.queries ?? "n/a"} queries: intent {e.intent_accuracy != null ? (e.intent_accuracy * 100).toFixed(1) + "%" : "n/a"}, company {e.company_accuracy != null ? (e.company_accuracy * 100).toFixed(1) + "%" : "n/a"}, metric {e.metric_accuracy != null ? (e.metric_accuracy * 100).toFixed(1) + "%" : "n/a"}</td></tr>
              <tr><td>Inference</td><td className="num">Pure numpy, deterministic argmax, no GPU</td></tr>
            </tbody>
          </table>
        </div>
        <div className="card">
          <div className="card-t">Data-quality handling</div>
          <div className="card-s">The report's as-reported principle is kept: nothing is corrected or imputed</div>
          <div style={{ display: "grid", gap: 10, marginTop: 12, fontSize: 13.5 }}>
            <div><b>{meta.flags.report_exclusions}</b> companies with values excluded from sector totals exactly as the report does (SIS Limited; Patel Engineering previous-year Scope 2).</div>
            <div><b>{meta.flags.magnitude_checks}</b> companies whose Scope 1+2 is below 0.1% of their sector median, likely filed in thousand or million tCO₂e. Shown as filed, not ranked.</div>
            <div><b>{meta.flags.unit_checks}</b> companies whose per-rupee intensity implies over 10,000 tCO₂e per crore. Shown as filed, not ranked on level.</div>
            <div>Physical-output intensity uses company-specific units, so only its year-on-year change is compared.</div>
            <div>The Rating sheet gives 100 when both years of a metric are reported as 0; this is disclosed wherever those scores appear.</div>
          </div>
        </div>
        <div className="card">
          <div className="card-t">AI-scored questions: two scoring runs</div>
          <div className="card-s">Company answers use the Rating sheet; aggregate answers quote the report and show the recount</div>
          <table className="mini-table" style={{ marginTop: 12 }}>
            <thead><tr><th>Table</th><th>Top level</th><th className="num">Report</th><th className="num">Rating sheet</th></tr></thead>
            <tbody>
              {Object.entries(div).map(([t, v]: any) => {
                const top = t === "2.2" ? v.levels[0] : v.levels[v.levels.length - 1];
                return <tr key={t}><td>Table {t} (Q{v.qid})</td><td>{top.label.slice(0, 38)}{top.label.length > 38 ? "…" : ""}</td><td className="num">{top.report}</td><td className="num">{top.rating_sheet}</td></tr>;
              })}
            </tbody>
          </table>
        </div>
        <div className="card">
          <div className="card-t">Guardrails</div>
          <div style={{ display: "grid", gap: 8, marginTop: 10, fontSize: 13.5 }}>
            {[
              "No web access and no free-text generation. Answers come only from the three source files.",
              "Other ESG themes (water, energy, waste, people, governance) are refused with a pointer to the right chapter of the report.",
              "Financial data, forecasts, investment advice and personal details are refused.",
              "Companies outside the 982 are named as absent, never substituted.",
              "Ambiguous names (for example Dalmia Bharat) trigger a clarification instead of a guess.",
              "Every numeric statement is checked for a citation before the answer is returned.",
            ].map((t) => <div key={t} style={{ display: "flex", gap: 8 }}><I.check style={{ width: 16, height: 16, color: "var(--good-ink)", flex: "none", marginTop: 3 }} /><span>{t}</span></div>)}
          </div>
        </div>
        <div className="card">
          <div className="card-t">Sources and privacy</div>
          <div style={{ display: "grid", gap: 8, marginTop: 10, fontSize: 13.5 }}>
            <div><b>E1 data.xlsx</b>: Questions, Base Data (raw responses) and Rating sheets.</div>
            <div><b>E1 chapter</b>: tables, key observations and insights.</div>
            <div><b>Business Responsibility and Sustainability in India</b> (IIMB, FY 2024-25): methodology and page references. <a href="/files/report.pdf" target="_blank" rel="noreferrer">Open PDF</a></div>
            <div className="muted">Dataset {meta.dataset.dataset_id}. No sign-in, no cookies for tracking. Conversations and your company lens are stored only in your browser.</div>
          </div>
          <div style={{ marginTop: 12 }}><button className="btn" onClick={() => onAsk("How do you avoid hallucinations?")}><I.shield />Ask how grounding works</button></div>
        </div>
      </div>
    </div>
  );
}
