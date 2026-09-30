import { scaleLinear, scaleLog, type ScaleContinuousNumeric } from "d3-scale";
import { hierarchy, treemap, treemapSquarify } from "d3-hierarchy";
import { useMemo, useState } from "react";
import { compact, useAnswer, useTip, useWidth } from "../../ui";

type Row = { id?: string; label: string; value: number; display: string; full?: string; rank?: number | null; highlight?: boolean };

function barPath(x0: number, x1: number, y: number, h: number, r = 4) {
  const w = x1 - x0;
  if (Math.abs(w) < 0.5) return "";
  const rr = Math.min(r, Math.abs(w), h / 2);
  if (w > 0) return `M${x0},${y}H${x1 - rr}Q${x1},${y} ${x1},${y + rr}V${y + h - rr}Q${x1},${y + h} ${x1 - rr},${y + h}H${x0}Z`;
  return `M${x0},${y}H${x1 + rr}Q${x1},${y} ${x1},${y + rr}V${y + h - rr}Q${x1},${y + h} ${x1 + rr},${y + h}H${x0}Z`;
}

function ticksFor(scale: ScaleContinuousNumeric<number, number>, log: boolean, n = 4): number[] {
  if (!log) return scale.ticks(n);
  const [a, b] = scale.domain();
  const out: number[] = [];
  for (let e = Math.ceil(Math.log10(a)); e <= Math.floor(Math.log10(b)); e++) out.push(Math.pow(10, e));
  if (out.length > 6) return out.filter((_, i) => i % 2 === 0);
  return out;
}

function onEntity(ask: (q: string) => void, id: string | undefined, label: string) {
  if (!id) return undefined;
  if (/^S\d+$/.test(id)) return () => ask(`Give me an overview of the ${label} sector`);
  return () => ask(`Show ${label}'s E1 profile`);
}

/* =============================================================== Bars */
export function Bars({ b }: { b: any }) {
  const rows: Row[] = b.rows || [];
  const { ask } = useAnswer();
  const [ref, w] = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTip();
  const hasHi = rows.some((r) => r.highlight);
  const ranks = rows.some((r) => r.rank);
  const labelW = Math.min(210, Math.max(110, w * 0.3));
  const rankW = ranks ? 30 : 0;
  const valW = 78;
  const plotW = Math.max(80, w - labelW - valW - rankW - 8);
  const rowH = 30;
  const top = 22;
  const H = top + rows.length * rowH + 6;
  const diverging = !!b.diverging;
  const vals = rows.map((r) => r.value);
  let scale: ScaleContinuousNumeric<number, number>;
  let x0: number;
  const log = !!b.log && !diverging && vals.some((v) => v > 0);
  if (diverging) {
    const M = Math.max(1e-9, ...vals.map((v) => Math.abs(v)), b.median ? Math.abs(b.median.value) : 0);
    scale = scaleLinear().domain([-M, M]).range([0, plotW]).nice();
    x0 = scale(0);
  } else if (log) {
    const pos = vals.filter((v) => v > 0);
    const mn = Math.min(...pos, b.median?.value > 0 ? b.median.value : Infinity);
    const mx = Math.max(...pos, b.median?.value || 0);
    scale = scaleLog().domain([Math.pow(10, Math.floor(Math.log10(mn))), mx * 1.05]).range([0, plotW]).clamp(true);
    x0 = 0;
  } else {
    const mx = b.max ?? Math.max(...vals, b.median?.value ?? 0, 1e-9);
    scale = scaleLinear().domain([0, mx]).range([0, plotW]).nice();
    x0 = 0;
  }
  const ticks = ticksFor(scale, log);
  const fmtTick = (t: number) => (diverging ? `${t > 0 ? "+" : t < 0 ? "−" : ""}${Math.abs(t)}%` : compact(t));
  const ox = labelW + rankW;
  return (
    <div ref={ref}>
      <svg className="chart" width={w} height={H} role="img" aria-label={b.title}>
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={ox + scale(t)} x2={ox + scale(t)} y1={top - 4} y2={H - 4} />
            <text className="axis-t" x={ox + scale(t)} y={12} textAnchor="middle">{fmtTick(t)}</text>
          </g>
        ))}
        <line className="base" x1={ox + x0} x2={ox + x0} y1={top - 4} y2={H - 4} />
        {rows.map((r, i) => {
          const y = top + i * rowH;
          const v = log ? Math.max(r.value, scale.domain()[0]) : r.value;
          const x1 = r.value <= 0 && log ? x0 : scale(v);
          const cls = diverging ? (r.value < 0 ? "neg" : "pos") : r.highlight ? "hi" : hasHi ? "" : "one";
          const click = onEntity(ask, r.id, r.label);
          const endX = diverging ? (r.value < 0 ? Math.min(x0, x1) - 6 : Math.max(x0, x1) + 6) : x1 + 6;
          const anchor = diverging && r.value < 0 ? "end" : "start";
          const inside = diverging && ((r.value < 0 && endX < 40) || (r.value >= 0 && endX > plotW - 40));
          return (
            <g key={i} className="bar-row" style={{ cursor: click ? "pointer" : "default" }} onClick={click}
               onMouseMove={(e) => show(e, r.label, [r.full || r.display, ...(r.rank ? [`Rank ${r.rank}`] : [])])} onMouseLeave={hide}>
              <rect x={0} y={y} width={w} height={rowH} fill="transparent" />
              {ranks && <text className="rank" x={labelW + rankW - 8} y={y + rowH / 2 + 4} textAnchor="end">{r.rank ?? ""}</text>}
              <text className={"lab" + (r.highlight ? " hi" : "")} x={labelW - 8} y={y + rowH / 2 + 4} textAnchor="end">
                {r.label.length > labelW / 6.6 ? r.label.slice(0, Math.floor(labelW / 6.6) - 1) + "…" : r.label}
              </text>
              <path className={"bar grow " + cls} d={barPath(ox + x0, ox + x1, y + 7, rowH - 14)} style={{ animationDelay: `${i * 22}ms`, transformOrigin: `${ox + x0}px center` }} />
              <text className={"val" + (r.highlight ? " hi" : "")} x={inside ? ox + (r.value < 0 ? x0 + 6 : x0 - 6) : ox + endX} y={y + rowH / 2 + 4}
                    textAnchor={inside ? (r.value < 0 ? "start" : "end") : anchor}>{r.display}</text>
            </g>
          );
        })}
        {b.median && isFinite(b.median.value) && (
          <g>
            <line className="med" x1={ox + scale(log ? Math.max(b.median.value, scale.domain()[0]) : b.median.value)} x2={ox + scale(log ? Math.max(b.median.value, scale.domain()[0]) : b.median.value)} y1={top - 6} y2={H - 4} />
          </g>
        )}
      </svg>
      <div className="legend">
        {b.median && <span><i className="line" style={{ background: "var(--ink-2)" }} />{b.median.label} {b.median.display}</span>}
        {log && <span className="muted">Log scale</span>}
        {diverging && <><span><i style={{ background: "var(--div-neg)" }} />Decrease</span><span><i style={{ background: "var(--div-pos)" }} />Increase</span></>}
        {hasHi && !diverging && <span><i style={{ background: "var(--focus)" }} />Selected company</span>}
      </div>
      {tip}
    </div>
  );
}

/* =============================================================== Strip (dot plot) */
export function Strip({ b }: { b: any }) {
  const pts: any[] = b.points || [];
  const [ref, w] = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTip();
  const { ask } = useAnswer();
  const H = 118;
  const padL = 12, padR = 12, cy = 58, band = 40;
  const vals = pts.map((p) => p.value);
  const diverging = !!b.diverging;
  const sorted = [...vals].sort((a, c) => a - c);
  const q = (k: number) => sorted[Math.max(0, Math.min(sorted.length - 1, Math.round(k * (sorted.length - 1))))];
  let scale: ScaleContinuousNumeric<number, number>;
  let lo: number, hi: number;
  const log = !!b.log && vals.some((v) => v > 0);
  if (log) {
    const pos = vals.filter((v) => v > 0);
    lo = Math.min(...pos);
    hi = Math.max(...pos);
    scale = scaleLog().domain([Math.pow(10, Math.floor(Math.log10(lo))), Math.pow(10, Math.ceil(Math.log10(hi)))]).range([padL, w - padR]).clamp(true);
  } else if (diverging) {
    lo = Math.min(q(0.03), -10);
    hi = Math.max(q(0.97), 10);
    scale = scaleLinear().domain([lo, hi]).range([padL, w - padR]).clamp(true).nice();
  } else {
    lo = Math.min(...vals, 0);
    hi = Math.max(...vals, 1e-9);
    scale = scaleLinear().domain([lo, hi]).range([padL, w - padR]).nice();
  }
  const ticks = ticksFor(scale, log, 5);
  const fmtT = (t: number) => (diverging ? `${t > 0 ? "+" : t < 0 ? "−" : ""}${Math.abs(t)}%` : compact(t));
  const focus = pts.find((p) => p.highlight);
  const X = (v: number) => scale(log ? Math.max(v, scale.domain()[0]) : v);
  return (
    <div ref={ref}>
      <svg className="chart" width={w} height={H} role="img" aria-label={b.title}>
        {b.q1 != null && b.q3 != null && (
          <rect className="iqr" x={X(b.q1)} y={cy - band / 2 - 4} width={Math.max(2, X(b.q3) - X(b.q1))} height={band + 8} rx={6} />
        )}
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={scale(t)} x2={scale(t)} y1={cy - band / 2 - 8} y2={cy + band / 2 + 8} />
            <text className="axis-t" x={scale(t)} y={H - 6} textAnchor="middle">{fmtT(t)}</text>
          </g>
        ))}
        {diverging && <line className="base" x1={scale(0)} x2={scale(0)} y1={cy - band / 2 - 8} y2={cy + band / 2 + 8} />}
        {b.median != null && <line className="med" x1={X(b.median)} x2={X(b.median)} y1={cy - band / 2 - 8} y2={cy + band / 2 + 8} />}
        {pts.map((p, i) => {
          if (p.highlight) return null;
          const jitter = (((i * 2654435761) % 1000) / 1000 - 0.5) * band;
          return (
            <g key={i} onMouseMove={(e) => show(e, p.label, [p.display])} onMouseLeave={hide} onClick={onEntity(ask, p.id, p.label)} style={{ cursor: "pointer" }}>
              <circle cx={X(p.value)} cy={cy + jitter} r={10} fill="transparent" />
              <circle className="dot" cx={X(p.value)} cy={cy + jitter} r={4} />
            </g>
          );
        })}
        {focus && (
          <g onMouseMove={(e) => show(e, focus.label, [focus.display])} onMouseLeave={hide}>
            <circle cx={X(focus.value)} cy={cy} r={12} fill="var(--focus)" opacity={0.14}>
              <animate attributeName="r" values="7;14;7" dur="2.4s" repeatCount="indefinite" />
            </circle>
            <circle className="dot hi" cx={X(focus.value)} cy={cy} r={6.5} />
            <text className="val hi" x={Math.min(Math.max(X(focus.value), 60), w - 60)} y={16} textAnchor="middle">{focus.label}: {focus.display}</text>
            <line x1={X(focus.value)} x2={X(focus.value)} y1={21} y2={cy - 8} stroke="var(--focus)" strokeWidth={1} />
          </g>
        )}
      </svg>
      <div className="legend">
        {focus && <span><i style={{ background: "var(--focus)", borderRadius: 99 }} />{focus.label}</span>}
        <span><i style={{ background: "var(--peer-strong)", borderRadius: 99 }} />Peers ({pts.length - (focus ? 1 : 0)})</span>
        {b.median_display && <span><i className="line" style={{ background: "var(--ink-2)" }} />Median {b.median_display}</span>}
        <span><i style={{ background: "var(--surface-3)" }} />Middle 50%</span>
        {log && <span className="muted">Log scale</span>}
        {diverging && <span className="muted">Extreme changes pinned at the edges</span>}
      </div>
      {tip}
    </div>
  );
}

/* =============================================================== Grouped */
const GREY = /median|other|2023-24|all companies/i;
function seriesColor(name: string, i: number, _n: number, all?: string[]) {
  if (GREY.test(name)) return "var(--peer-strong)";
  const coloured = (all || []).filter((s) => !GREY.test(s));
  const k = all ? coloured.indexOf(name) : i;
  return `var(--s${(Math.max(0, k) % 8) + 1})`;
}

export function Grouped({ b }: { b: any }) {
  const groups: any[] = b.groups || [];
  const series: string[] = b.series || [];
  const [ref, w] = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTip();
  const labelW = Math.min(220, Math.max(110, w * 0.32));
  const valW = 64;
  const plotW = Math.max(80, w - labelW - valW - 6);
  const bh = 11, gap = 3;
  const gh = series.length * (bh + gap) + 14;
  const top = 20;
  const H = top + groups.length * gh + 4;
  const all = groups.flatMap((g) => g.values).filter((v: any) => v != null) as number[];
  const log = !!b.log && all.some((v) => v > 0);
  const scale: ScaleContinuousNumeric<number, number> = log
    ? scaleLog().domain([Math.pow(10, Math.floor(Math.log10(Math.min(...all.filter((v) => v > 0))))), Math.max(...all) * 1.05]).range([0, plotW]).clamp(true)
    : scaleLinear().domain([0, b.max ?? Math.max(...all, 1e-9)]).range([0, plotW]).nice();
  const ticks = ticksFor(scale, log);
  return (
    <div ref={ref}>
      <svg className="chart" width={w} height={H} role="img" aria-label={b.title}>
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={labelW + scale(t)} x2={labelW + scale(t)} y1={top - 4} y2={H - 2} />
            <text className="axis-t" x={labelW + scale(t)} y={12} textAnchor="middle">{compact(t)}{b.unit === "%" ? "%" : ""}</text>
          </g>
        ))}
        <line className="base" x1={labelW} x2={labelW} y1={top - 4} y2={H - 2} />
        {groups.map((g, gi) => {
          const y0 = top + gi * gh + 6;
          return (
            <g key={gi}>
              <text className="lab" x={labelW - 8} y={y0 + (series.length * (bh + gap)) / 2 + 3} textAnchor="end">
                {g.label.length > labelW / 6.6 ? g.label.slice(0, Math.floor(labelW / 6.6) - 1) + "…" : g.label}
              </text>
              {series.map((s, si) => {
                const v = g.values[si];
                const y = y0 + si * (bh + gap);
                if (v == null) return <text key={si} className="axis-t" x={labelW + 6} y={y + bh - 2}>n/a</text>;
                const x1 = scale(log ? Math.max(v, scale.domain()[0]) : v);
                return (
                  <g key={si} onMouseMove={(e) => show(e, `${g.label}`, [`${s}: ${g.displays?.[si] ?? v}`, ...(g.counts ? [`${g.counts[si]} companies`] : [])])} onMouseLeave={hide}>
                    <path className="grow" d={barPath(labelW, labelW + x1, y, bh, 3)} style={{ fill: seriesColor(s, si, series.length, series), animationDelay: `${gi * 40 + si * 20}ms`, transformOrigin: `${labelW}px center` }} />
                    <text className="val" x={labelW + x1 + 5} y={y + bh - 1.5} fontSize={11}>{g.displays?.[si]}</text>
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
      <div className="legend">
        {series.map((s, i) => <span key={s}><i style={{ background: seriesColor(s, i, series.length, series) }} />{s}</span>)}
        {log && <span className="muted">Log scale</span>}
      </div>
      {tip}
    </div>
  );
}

/* =============================================================== Stack */
const ORD = ["var(--seq-1)", "var(--seq-3)", "var(--seq-5)", "var(--seq-7)", "var(--seq-9)"];
function segStyle(s: any, idx: number, b: any): React.CSSProperties {
  if (b.ordinal && s.score != null) {
    const k = [0, 25, 50, 75, 100].indexOf(s.score);
    return { background: ORD[Math.max(0, k)], color: k >= 3 ? "#fff" : "var(--ink)" };
  }
  if (b.categorical) return { background: `var(--s${(idx % 8) + 1})`, color: "#fff" };
  return {};
}

export function Stack({ b }: { b: any }) {
  const { tip, show, hide } = useTip();
  const rows: any[] = b.rows || [];
  const legend: any[] = [];
  const seen = new Set<string>();
  rows.forEach((r) => r.segments.forEach((s: any, i: number) => {
    const key = b.ordinal ? String(s.score) : s.label;
    if (!seen.has(key)) {
      seen.add(key);
      legend.push({ s, i });
    }
  }));
  return (
    <div>
      {rows.map((r, ri) => {
        const total = r.segments.reduce((a: number, s: any) => a + s.value, 0) || 1;
        return (
          <div className="stack-row" key={ri}>
            <div className="stack-l" title={r.label}>{r.label}</div>
            <div className="stack-bar">
              {r.segments.map((s: any, i: number) => {
                const pct = (100 * s.value) / total;
                if (s.value <= 0) return null;
                return (
                  <div key={i} className={`seg ${s.tone || ""} ${s.highlight ? "hl" : ""}`} style={{ width: `${pct}%`, animationDelay: `${ri * 80 + i * 40}ms`, ...segStyle(s, i, b) }}
                       onMouseMove={(e) => show(e, s.label, [`${s.value} of ${total} (${pct.toFixed(1)}%)`])} onMouseLeave={hide}>
                    {pct >= 7 && <span>{s.value}</span>}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
      <div className="legend">
        {legend.map(({ s, i }) => (
          <span key={i + s.label}>
            <i style={{ ...(s.tone === "pos" ? { background: "var(--s1)" } : s.tone === "neg" ? { background: "var(--peer)" } : s.tone === "muted" ? { background: "var(--surface-3)" } : {}), ...segStyle(s, i, b) }} />
            {b.ordinal ? `Score ${s.score}` : s.label}
          </span>
        ))}
      </div>
      {tip}
    </div>
  );
}

/* =============================================================== Radar */
export function Radar({ b }: { b: any }) {
  const axes: string[] = b.axes;
  const series: any[] = b.series;
  const [ref, w] = useWidth<HTMLDivElement>();
  const size = Math.min(w, 360);
  const cx = size / 2, cy = size / 2 + 4, R = size / 2 - 46;
  const ang = (i: number) => -Math.PI / 2 + (2 * Math.PI * i) / axes.length;
  const pt = (i: number, v: number) => [cx + Math.cos(ang(i)) * (R * v) / 100, cy + Math.sin(ang(i)) * (R * v) / 100];
  return (
    <div ref={ref} style={{ display: "flex", flexWrap: "wrap", gap: 18, alignItems: "center" }}>
      <svg className="chart" width={size} height={size + 8} role="img" aria-label={b.title}>
        {[25, 50, 75, 100].map((r) => (
          <polygon key={r} points={axes.map((_, i) => pt(i, r).join(",")).join(" ")} fill="none" stroke="var(--grid)" />
        ))}
        {axes.map((a, i) => {
          const [x, y] = pt(i, 116);
          const [x2, y2] = pt(i, 100);
          return (
            <g key={a}>
              <line x1={cx} y1={cy} x2={x2} y2={y2} stroke="var(--grid)" />
              <text className="lab" x={x} y={y + 4} textAnchor="middle">{a}</text>
            </g>
          );
        })}
        {series.map((s, si) => {
          const pts = s.values.map((v: number | null, i: number) => pt(i, v ?? 0).join(",")).join(" ");
          const col = `var(--s${si + 1})`;
          return (
            <g key={si} style={{ animation: `fade .6s ${si * 150}ms both` }}>
              <polygon points={pts} fill={col} fillOpacity={0.1} stroke={col} strokeWidth={2} strokeLinejoin="round" />
              {s.values.map((v: number | null, i: number) => {
                const [x, y] = pt(i, v ?? 0);
                return <circle key={i} cx={x} cy={y} r={4} fill={col} stroke="var(--surface)" strokeWidth={2} />;
              })}
            </g>
          );
        })}
      </svg>
      <div className="legend" style={{ flexDirection: "column", gap: 8 }}>
        {series.map((s, si) => (
          <span key={si}><i style={{ background: `var(--s${si + 1})` }} />{s.name}: {s.values.map((v: number | null) => (v == null ? "n/a" : v.toFixed(0))).join(" / ")}</span>
        ))}
        <span className="muted">Governance / Action / Performance, 0 to 100</span>
      </div>
    </div>
  );
}

/* =============================================================== Treemap */
export function Treemap({ b }: { b: any }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTip();
  const { ask } = useAnswer();
  const H = Math.max(300, Math.min(440, w * 0.55));
  const nodes = useMemo(() => {
    const root = hierarchy({ children: b.items } as any).sum((d: any) => d.value || 0);
    treemap<any>().tile(treemapSquarify.ratio(1.3)).size([w, H]).paddingInner(2).round(true)(root);
    return root.leaves() as any[];
  }, [b.items, w, H]);
  return (
    <div ref={ref}>
      <svg className="chart" width={w} height={H} role="img" aria-label={b.title}>
        {nodes.map((n, i) => {
          const d = n.data;
          const ww = n.x1 - n.x0, hh = n.y1 - n.y0;
          const fits = ww > 70 && hh > 34;
          const op = 0.35 + 0.65 * Math.min(1, d.share / 25);
          return (
            <g key={d.id} onMouseMove={(e) => show(e, d.label, [d.display, `${d.share}% of total`])} onMouseLeave={hide}
               onClick={() => ask(`Give me an overview of the ${d.label} sector`)} style={{ cursor: "pointer", animation: `fade .5s ${i * 25}ms both` }}>
              <rect x={n.x0} y={n.y0} width={ww} height={hh} rx={4} fill="var(--s1)" fillOpacity={op} />
              {fits && (
                <>
                  <text x={n.x0 + 8} y={n.y0 + 18} style={{ fill: op > 0.6 ? "#fff" : "var(--ink)", fontSize: 12.5, fontWeight: 600 }}>
                    {d.short.length > ww / 7.5 ? d.short.slice(0, Math.floor(ww / 7.5) - 1) + "…" : d.short}
                  </text>
                  <text x={n.x0 + 8} y={n.y0 + 33} style={{ fill: op > 0.6 ? "#fff" : "var(--ink-2)", fontSize: 11.5 }}>{d.share}%</text>
                </>
              )}
            </g>
          );
        })}
      </svg>
      <div className="legend"><span className="muted">Area is proportional to emissions; shade deepens with share. Click a sector to open it.</span></div>
      {tip}
    </div>
  );
}

/* =============================================================== Position (peer percentiles) */
export function Position({ b }: { b: any }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTip();
  const chartW = w < 640 ? w - 20 : Math.max(160, w - 210 - 76 - 28);
  return (
    <div ref={ref}>
      <div className="pos">
        <div className="pos-row" style={{ marginBottom: -6 }}>
          <div />
          <div className="axis-t" style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--ink-3)" }}>
            <span>worse than peers</span><span>better than peers</span>
          </div>
          <div className="axis-t" style={{ textAlign: "right", fontSize: 11, color: "var(--ink-3)" }}>beats</div>
        </div>
        {b.rows.map((r: any, i: number) => {
          const pts: any[] = r.points || [];
          let scale: ScaleContinuousNumeric<number, number> | null = null;
          if (pts.length) {
            const vals = pts.map((p) => p.value);
            const lower = r.better === "lower";
            let lo = Math.min(...vals), hi = Math.max(...vals);
            if (r.yoy) {
              const s = [...vals].sort((a, c) => a - c);
              lo = Math.min(s[Math.floor(s.length * 0.05)], -5);
              hi = Math.max(s[Math.ceil(s.length * 0.95) - 1], 5);
            }
            const range = lower ? [chartW - 8, 8] : [8, chartW - 8];
            scale = r.log && lo > 0 ? scaleLog().domain([lo, hi]).range(range).clamp(true) : scaleLinear().domain([lo, hi === lo ? lo + 1 : hi]).range(range).clamp(true);
          }
          return (
            <div className="pos-row" key={i} style={{ animation: `rise .5s ${i * 60}ms both` }}>
              <div className="pos-l">{r.label}<small>{r.display}{r.median_display ? ` · median ${r.median_display}` : ""}</small></div>
              <div className="pos-chart">
                {scale ? (
                  <svg className="chart" width={chartW} height={30}>
                    <line className="base" x1={4} x2={chartW - 4} y1={15} y2={15} />
                    {pts.filter((p) => !p.focus).map((p, j) => {
                      const x = scale!(r.log ? Math.max(p.value, (scale!.domain() as number[])[0]) : p.value);
                      return <circle key={j} className="dot" cx={x} cy={15 + ((((j * 7919) % 13) / 13) - 0.5) * 12} r={3} onMouseMove={(e) => show(e, p.label, [String(p.value.toLocaleString("en-US", { maximumFractionDigits: 2 }))])} onMouseLeave={hide} />;
                    })}
                    {pts.filter((p) => p.focus).map((p, j) => (
                      <circle key={"f" + j} className="dot hi" cx={scale!(r.log ? Math.max(p.value, (scale!.domain() as number[])[0]) : p.value)} cy={15} r={6.5} />
                    ))}
                  </svg>
                ) : <span className="muted" style={{ fontSize: 12.5 }}>No comparable data ({r.n} peers reporting)</span>}
              </div>
              <div className="pos-p">
                <b>{r.percentile == null ? "n/a" : `${r.percentile}%`}</b>
                <span>of {Math.max(0, (r.n || 1) - 1)} peers</span>
              </div>
            </div>
          );
        })}
      </div>
      <div className="legend"><span><i style={{ background: "var(--focus)", borderRadius: 99 }} />{b.company}</span><span><i style={{ background: "var(--peer-strong)", borderRadius: 99 }} />Sector peers</span><span className="muted">Each scale is oriented so that better is to the right</span></div>
      {tip}
    </div>
  );
}

/* =============================================================== Score grid */
function heat(score: number | null | undefined): React.CSSProperties {
  if (score == null) return { background: "var(--surface-2)", color: "var(--ink-3)" };
  const k = Math.round(score / 25);
  return { background: ORD[Math.max(0, Math.min(4, k))], color: k >= 3 ? "#fff" : "var(--ink)" };
}
export { heat };

export function ScoreGrid({ b }: { b: any }) {
  let last = "";
  return (
    <div className="sgrid">
      <div className="sg-head"><span>Question</span><span style={{ textAlign: "center" }}>{b.company?.slice(0, 10)}</span><span style={{ textAlign: "center" }}>Median</span><span className="t">0 to 100</span></div>
      {b.rows.map((r: any, i: number) => {
        const head = r.section !== last ? (last = r.section) : null;
        return (
          <div key={r.qid}>
            {head && <div className="sg-sec">{head}</div>}
            <div className="sg-row" style={{ animation: `fade .4s ${i * 18}ms both` }}>
              <span className="l" title={`Q${r.qid}: ${r.label}`}>{r.label}</span>
              <span className="sg-cell" style={heat(r.score)}>{r.score ?? "n/a"}</span>
              <span className="sg-cell" style={heat(r.median)}>{r.median == null ? "n/a" : Math.round(r.median)}</span>
              <span className="sg-track">
                {r.median != null && <i className="md" style={{ left: `calc(${r.median}% - 1.5px)` }} />}
                {r.score != null && <i className="me" style={{ left: `calc(${r.score}% - 1.5px)` }} />}
              </span>
            </div>
          </div>
        );
      })}
      <div className="legend"><span><i style={{ background: "var(--focus)" }} />{b.company}</span><span><i style={{ background: "var(--ink-3)" }} />Sector median</span><span className="muted">Scores from the Rating sheet</span></div>
    </div>
  );
}

/* =============================================================== Simulator */
function rateRatio(r: number) {
  if (r > 1.05) return 0;
  if (r > 1) return 25;
  if (r === 1) return 50;
  if (r >= 0.95) return 75;
  return 100;
}

export function Simulator({ b }: { b: any }) {
  const [p, setP] = useState<number>(b.pct ?? 10);
  const [ref, w] = useWidth<HTMLDivElement>();
  const peers: any[] = b.peers;
  const nv = b.cy * (1 - p / 100);
  const ratio = b.py ? nv / b.py : null;
  const score = ratio != null && b.rating_q ? rateRatio(ratio) : null;
  const rankOf = (val: number) => 1 + peers.filter((x) => x.id !== b.company_id && (x.value > val || (x.value === val && x.label.toLowerCase() < b.company.toLowerCase()))).length;
  const r0 = rankOf(b.cy), r1 = rankOf(nv);
  const vals = peers.map((x) => x.value).filter((v) => v > 0);
  const log = b.kind === "abs" && vals.length > 2 && Math.max(...vals) / Math.min(...vals) > 200;
  const cw = Math.max(240, w < 640 ? w : w / 2 - 12);
  const scale: ScaleContinuousNumeric<number, number> = log
    ? scaleLog().domain([Math.min(...vals), Math.max(...vals)]).range([10, cw - 10]).clamp(true)
    : scaleLinear().domain([0, Math.max(...peers.map((x) => x.value), b.cy)]).range([10, cw - 10]).nice();
  const fmt = (v: number) => v.toLocaleString("en-US", { maximumFractionDigits: v < 10 ? 3 : 0 });
  return (
    <div ref={ref} className="sim">
      <div className="sim-ctrl">
        <div>
          <div className="card-s">Cut to FY 2024-25 {b.metric.toLowerCase()}</div>
          <div className="sim-pct tnum">{p}%<small>lower</small></div>
        </div>
        <input className="rng" type="range" min={0} max={60} step={1} value={p} onChange={(e) => setP(Number(e.target.value))} aria-label="Reduction percentage" />
        <div className="presets">
          {[5, 10, 20, 30, 50].map((x) => <button key={x} className={"tool" + (p === x ? " on" : "")} onClick={() => setP(x)}>{x}%</button>)}
          {b.need_pct > 0 && b.need_pct < 100 && <button className={"tool" + (Math.abs(p - Math.ceil(b.need_pct)) < 0.5 ? " on" : "")} onClick={() => setP(Math.min(60, Math.ceil(b.need_pct)))}>To median ({b.need_pct.toFixed(1)}%)</button>}
        </div>
        <div className="sim-out">
          <div><div className="k">New value</div><div className="v tnum">{fmt(nv)}<small>{b.unit}</small></div></div>
          <div><div className="k">Year-on-year ratio</div><div className="v tnum">{ratio == null ? "n/a" : ratio.toFixed(3)}</div></div>
          <div><div className="k">Rating Q{b.rating_q ?? "n/a"}</div><div className="v tnum">{score ?? "n/a"}<small>was {b.current_score ?? "n/a"}</small></div></div>
          <div><div className="k">Rank in {b.sector}</div><div className="v tnum">{r1}<small>of {peers.length}, was {r0}</small></div></div>
        </div>
      </div>
      <div>
        <div className="card-s" style={{ marginBottom: 8 }}>Position among {peers.length} {b.sector} companies{log ? " (log scale)" : ""}</div>
        <svg className="chart" width={cw} height={150}>
          <line className="base" x1={10} x2={cw - 10} y1={80} y2={80} />
          {b.median != null && <><line className="med" x1={scale(b.median)} x2={scale(b.median)} y1={54} y2={106} /><text className="med-t" x={scale(b.median)} y={122} textAnchor="middle">median</text></>}
          {peers.filter((x) => x.id !== b.company_id).map((x, i) => (
            <circle key={i} className="dot" cx={scale(Math.max(x.value, (scale.domain() as number[])[0]))} cy={80 + ((((i * 2654435761) % 1000) / 1000) - 0.5) * 34} r={3.5} />
          ))}
          <circle cx={scale(b.cy)} cy={80} r={7} fill="none" stroke="var(--ink-3)" strokeWidth={1.5} strokeDasharray="0" />
          <line x1={scale(b.cy)} x2={scale(Math.max(nv, (scale.domain() as number[])[0]))} y1={80} y2={80} stroke="var(--focus)" strokeWidth={2} />
          <circle className="dot hi" cx={scale(Math.max(nv, (scale.domain() as number[])[0]))} cy={80} r={7} style={{ transition: "cx .25s var(--ease)" }} />
          <text className="val hi" x={Math.min(Math.max(scale(Math.max(nv, (scale.domain() as number[])[0])), 50), cw - 50)} y={40} textAnchor="middle">{b.company}</text>
        </svg>
        <div className="legend"><span><i style={{ background: "transparent", border: "1.5px solid var(--ink-3)", borderRadius: 99 }} />Reported</span><span><i style={{ background: "var(--focus)", borderRadius: 99 }} />Scenario</span></div>
      </div>
    </div>
  );
}
