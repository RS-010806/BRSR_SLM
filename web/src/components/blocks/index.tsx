import { lazy, Suspense, useState } from "react";
import type { Block } from "../../api";
import { blockSheet, downloadBlock } from "../../exporting";
import { I } from "../../icons";
import { Card, CiteChip } from "../../ui";
import { Bars, Grouped, Position, Simulator, Stack, Strip, Treemap } from "./Charts";
import { Action, Callout, Capabilities, Checklist, Choices, Compare, Kpis, Links, Names, Points, Quotes, Table } from "./Content";

const Infographic = lazy(() => import("./Infographic").then((m) => ({ default: m.Infographic })));

const fmtCell = (v: any) =>
  typeof v === "number" ? v.toLocaleString("en-US", { maximumFractionDigits: Math.abs(v) < 100 ? 2 : 0 }) : v == null ? "" : String(v);

/* Every chart has a table twin so no value is gated behind hover or colour. */
function asTable(b: Block): { columns: any[]; rows: any[] } | null {
  const s = blockSheet(b);
  if (!s) return null;
  return {
    columns: s.columns.map((label, i) => ({ key: "c" + i, label, align: s.rows.some((r) => typeof r[i] === "number") ? "right" : undefined })),
    rows: s.rows.map((r) => Object.fromEntries(r.map((v, i) => ["c" + i, fmtCell(v)]))),
  };
}

function Excel({ b }: { b: Block }) {
  if (!b.export) return null;
  return <button className="tool" title="Download as Excel" aria-label="Download as Excel" onClick={() => downloadBlock(b)}><I.download style={{ width: 12, height: 12, verticalAlign: -2 }} /> Excel</button>;
}

function ChartCard({ b, i, children }: { b: Block; i: number; children: React.ReactNode }) {
  const [mode, setMode] = useState<"chart" | "table">("chart");
  const t = asTable(b);
  const tools = (
    <>
      {b.cite && <CiteChip refText={b.cite} />}
      {t && <button className={"tool" + (mode === "chart" ? " on" : "")} onClick={() => setMode("chart")}>Chart</button>}
      {t && <button className={"tool" + (mode === "table" ? " on" : "")} onClick={() => setMode("table")}>Table</button>}
      <Excel b={b} />
    </>
  );
  return (
    <Card title={b.title} subtitle={b.subtitle} tools={tools} delay={i * 70}>
      {mode === "table" && t ? <Table b={t} /> : children}
    </Card>
  );
}

export function BlockView({ b, i }: { b: Block; i: number }) {
  switch (b.type) {
    case "kpis": return <Kpis b={b} />;
    case "bars": return <ChartCard b={b} i={i}><Bars b={b} /></ChartCard>;
    case "strip": return <ChartCard b={b} i={i}><Strip b={b} /></ChartCard>;
    case "grouped": return <ChartCard b={b} i={i}><Grouped b={b} /></ChartCard>;
    case "stack": return <ChartCard b={b} i={i}><Stack b={b} /></ChartCard>;
    case "treemap": return <ChartCard b={b} i={i}><Treemap b={b} /></ChartCard>;
    case "position": return <ChartCard b={b} i={i}><Position b={b} /></ChartCard>;
    case "simulator": return <Card title="What-if" subtitle="Drag the slider to try a different cut." delay={i * 70}><Simulator b={b} /></Card>;
    case "checklist": return <Card title={b.title} delay={i * 70}><Checklist b={b} /></Card>;
    case "points": return <Points b={b} />;
    case "names": return <Card title={b.title} subtitle={b.sector ? `${b.sector} · select a company to see its figures` : "Select a company to see its figures"} tools={<Excel b={b} />} delay={i * 70}><Names b={b} /></Card>;
    case "quotes": return b.title ? <Card title={b.title} delay={i * 70}><Quotes b={b} /></Card> : <Quotes b={b} />;
    case "table": return <Card title={b.title} tools={<Excel b={b} />} delay={i * 70}><Table b={b} /></Card>;
    case "compare": return <Card title={b.title} tools={<Excel b={b} />} delay={i * 70}><Compare b={b} /></Card>;
    case "infographic": return <Suspense fallback={<div className="skeleton" style={{ height: 320 }} />}><Infographic b={b} /></Suspense>;
    case "action": return <Action b={b} />;
    case "choices": return <Choices b={b} />;
    case "capabilities": return <Capabilities b={b} />;
    case "links": return <Card title={b.title} delay={i * 70}><Links b={b} /></Card>;
    case "callout": return <Callout b={b} />;
    case "learned": return b.items?.length ? (
      <Card title="Remembered for this conversation" delay={i * 70}>
        <div className="learned-card">{b.items.map((it: any) => <div className="li" key={it.key}><span>{it.label}</span><b>{it.value}</b></div>)}</div>
      </Card>
    ) : null;
    default: return null;
  }
}
