import { useEffect, useMemo, useState } from "react";
import type { Meta } from "../api";
import { SOURCE_NOTE } from "../exporting";
import { I } from "../icons";
import { compact } from "../ui";
import { downloadXlsx } from "../xlsx";

const fmtPct = (v: number | null) => (v == null ? "n/a" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}%`);
const fmtNum = (v: number | null) => (v == null ? null : v.toLocaleString("en-US", { maximumFractionDigits: Math.abs(v) < 100 ? 2 : 0 }));

/* ---------------------------------------------------------------- companies */
export function CompaniesPage({ onAsk, meta }: { onAsk: (q: string) => void; meta: Meta | null }) {
  const [rows, setRows] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [sector, setSector] = useState("");
  const [sort, setSort] = useState<{ k: string; d: number }>({ k: "short", d: 1 });
  const [limit, setLimit] = useState(100);
  useEffect(() => { fetch("/api/directory").then((r) => r.json()).then(setRows); }, []);
  const list = useMemo(() => {
    const s = q.toLowerCase();
    const f = rows.filter((r) => (!sector || r.sector === sector) && (!s || r.name.toLowerCase().includes(s)));
    return f.sort((a, b) => {
      const x = a[sort.k], y = b[sort.k];
      if (typeof x === "string" || typeof y === "string") return String(x).localeCompare(String(y)) * sort.d;
      if (x == null && y == null) return a.name.localeCompare(b.name);
      if (x == null) return 1;
      if (y == null) return -1;
      return (Number(x) - Number(y)) * sort.d || a.name.localeCompare(b.name);
    });
  }, [rows, q, sector, sort]);
  const th = (k: string, label: string, r = false) => (
    <th className={r ? "r" : ""} onClick={() => setSort(sort.k === k ? { k, d: -sort.d } : { k, d: k === "short" || k === "sector_name" ? 1 : -1 })}>
      {label}{sort.k === k ? (sort.d === 1 ? " ↑" : " ↓") : ""}
    </th>
  );
  const excel = () =>
    downloadXlsx("Companies GHG disclosures FY2024-25", [{
      name: "Companies", title: "GHG disclosures by company, FY 2024-25", note: SOURCE_NOTE,
      columns: ["Company", "Sector", "Scope 1 (tCO2e)", "Scope 2 (tCO2e)", "Scope 3 (tCO2e)", "Emission intensity (tCO2e per INR crore)",
        "Change in Scope 1 + Scope 2 vs FY 2023-24 (%)", "GHG emissions independently assured", "Reports Scope 3", "Projects to reduce GHG emissions"],
      rows: list.map((r) => [r.name, r.sector_name, r.s1, r.s2, r.s3, r.intensity, r.s12_yoy == null ? null : Math.round(r.s12_yoy * 100) / 100,
        r.assured ? "Yes" : "No", r.scope3 ? "Yes" : "No", r.projects ? "Yes" : "No"]),
    }]);
  return (
    <div className="page">
      <div className="page-h">
        <div>
          <h1>Companies</h1>
          <p>{rows.length ? `${rows.length} companies` : "Companies"} and what they disclosed for FY 2024-25. Select a company to see more.</p>
        </div>
        <button className="btn" onClick={excel} disabled={!rows.length}><I.download />Download Excel</button>
      </div>
      <div className="filters">
        <input className="input" placeholder="Search by name" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search by name" />
        <select className="select" value={sector} onChange={(e) => setSector(e.target.value)} aria-label="Sector">
          <option value="">All sectors</option>
          {meta?.sectors.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.n})</option>)}
        </select>
      </div>
      <div className="tbl-wrap" style={{ maxHeight: "none", background: "var(--surface)" }}>
        <table className="tbl">
          <thead>
            <tr>
              {th("short", "Company")}{th("sector_name", "Sector")}{th("s1", "Scope 1 (tCO₂e)", true)}{th("s2", "Scope 2 (tCO₂e)", true)}
              {th("s3", "Scope 3 (tCO₂e)", true)}{th("s12_yoy", "Change in Scope 1 + 2", true)}{th("assured", "Assured")}{th("scope3", "Reports Scope 3")}
            </tr>
          </thead>
          <tbody>
            {list.slice(0, limit).map((r) => (
              <tr key={r.id}>
                <td className="co"><button className="colink" onClick={() => onAsk(`Tell me about ${r.short}`)}>{r.short}</button>{r.unit_note && <span title="Disclosed in a unit that appears to differ from most filings" className="unit-flag">*</span>}</td>
                <td>{r.sector_name}</td>
                <td className="r" title={fmtNum(r.s1) || ""}>{r.s1 == null ? <span className="muted">Not disclosed</span> : compact(r.s1)}</td>
                <td className="r" title={fmtNum(r.s2) || ""}>{r.s2 == null ? <span className="muted">Not disclosed</span> : compact(r.s2)}</td>
                <td className="r" title={fmtNum(r.s3) || ""}>{r.s3 == null ? <span className="muted">Not disclosed</span> : compact(r.s3)}</td>
                <td className="r">{fmtPct(r.s12_yoy)}</td>
                <td className={r.assured ? "yes" : "no"}>{r.assured ? "Yes" : "No"}</td>
                <td className={r.scope3 ? "yes" : "no"}>{r.scope3 ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {list.length > limit && <div style={{ textAlign: "center", marginTop: 14 }}><button className="btn" onClick={() => setLimit(limit + 200)}>Show more ({list.length - limit} more)</button></div>}
      <p className="muted" style={{ fontSize: 12.5, marginTop: 14 }}>
        * The figure appears to be disclosed in a different unit from most filings. It is shown as disclosed.
      </p>
    </div>
  );
}

/* ---------------------------------------------------------------- sectors */
export function SectorsPage({ onAsk }: { onAsk: (q: string) => void }) {
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => { fetch("/api/sectors").then((r) => r.json()).then(setRows); }, []);
  const max = Math.max(1, ...rows.map((r) => r.share));
  const sorted = [...rows].sort((a, b) => b.share - a.share);
  const excel = () =>
    downloadXlsx("Sectors GHG disclosures FY2024-25", [{
      name: "Sectors", title: "GHG disclosures by sector, FY 2024-25", note: SOURCE_NOTE,
      columns: ["Sector", "Companies", "Scope 1 (tCO2e)", "Scope 2 (tCO2e)", "Scope 1 + Scope 2 (tCO2e)", "Share of total (%)",
        "Change vs FY 2023-24 (%)", "Companies with independent assurance", "Companies reporting Scope 3", "Companies with reduction projects"],
      rows: sorted.map((s) => [s.name, s.n, s.s1, s.s2, s.s12, Math.round(s.share * 100) / 100, s.yoy == null ? null : Math.round(s.yoy * 100) / 100, s.assured, s.scope3, s.projects]),
    }]);
  return (
    <div className="page">
      <div className="page-h">
        <div>
          <h1>Sectors</h1>
          <p>Sectors ordered by their share of disclosed Scope 1 and Scope 2 emissions for FY 2024-25. Select a sector for an overview.</p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button className="btn" onClick={() => onAsk("Which sector emits the most?")}><I.grid />Compare sectors</button>
          <button className="btn" onClick={excel} disabled={!rows.length}><I.download />Download Excel</button>
        </div>
      </div>
      <div className="sector-grid">
        {sorted.map((s, i) => (
          <button key={s.id} className="sector-card" onClick={() => onAsk(`Give me an overview of the ${s.name} sector`)} style={{ animation: `rise .45s ${i * 25}ms both` }}>
            <div className="sc-top"><span className="sc-name">{s.name}</span><span className="sc-code">{s.n} companies</span></div>
            <div className="spark" title={`${s.share.toFixed(1)}% of disclosed Scope 1 and Scope 2 emissions`}><i style={{ width: `${(100 * s.share) / max}%` }} /></div>
            <div className="sc-stats">
              <div className="sc-stat"><b>{compact(s.s1)}</b><span>Scope 1, tCO₂e</span></div>
              <div className="sc-stat"><b>{compact(s.s2)}</b><span>Scope 2, tCO₂e</span></div>
              <div className="sc-stat"><b>{s.share.toFixed(1)}%</b><span>of all sectors</span></div>
            </div>
            <div className="sc-stats">
              <div className="sc-stat"><b>{fmtPct(s.yoy)}</b><span>vs FY 2023-24</span></div>
              <div className="sc-stat"><b>{Math.round((100 * s.assured) / s.n)}%</b><span>assured</span></div>
              <div className="sc-stat"><b>{Math.round((100 * s.scope3) / s.n)}%</b><span>report Scope 3</span></div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
