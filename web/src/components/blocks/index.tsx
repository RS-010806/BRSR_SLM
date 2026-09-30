import { useState } from "react";
import type { Block } from "../../api";
import { I } from "../../icons";
import { Card, CiteChip } from "../../ui";
import { Bars, Grouped, Position, Radar, ScoreGrid, Simulator, Stack, Strip, Treemap } from "./Charts";
import { Callout, Capabilities, Checklist, Choices, Compare, Gap, Insights, Kpis, Links, Matrix, Quotes, ReportQuotes, Rubric, Table, tableCsv } from "./Content";

function download(name: string, text: string) {
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 500);
}

/* Every chart has a table twin so no value is gated behind hover or colour. */
function asTable(b: Block): { columns: any[]; rows: any[] } | null {
  if (b.type === "bars") return { columns: [{ key: "rank", label: "#" }, { key: "label", label: "Item" }, { key: "full", label: "Value", align: "right" }], rows: b.rows.map((r: any, i: number) => ({ rank: r.rank ?? i + 1, label: r.label, full: r.full || r.display, highlight: r.highlight })) };
  if (b.type === "strip") return { columns: [{ key: "label", label: "Company" }, { key: "display", label: "Value", align: "right" }], rows: [...b.points].sort((x: any, y: any) => y.value - x.value).map((p: any) => ({ label: p.label, display: p.display, highlight: p.highlight })) };
  if (b.type === "grouped") return { columns: [{ key: "label", label: "Item" }, ...b.series.map((s: string, i: number) => ({ key: "s" + i, label: s, align: "right" }))], rows: b.groups.map((g: any) => Object.fromEntries([["label", g.label], ...b.series.map((_: string, i: number) => ["s" + i, g.displays?.[i] ?? "n/a"])])) };
  if (b.type === "stack") {
    const labels: string[] = [];
    b.rows.forEach((r: any) => r.segments.forEach((s: any) => { const l = b.ordinal ? `Score ${s.score}` : s.label; if (!labels.includes(l)) labels.push(l); }));
    return { columns: [{ key: "row", label: "" }, ...labels.map((l, i) => ({ key: "c" + i, label: l, align: "right" }))], rows: b.rows.map((r: any) => Object.fromEntries([["row", r.label], ...labels.map((l, i) => ["c" + i, r.segments.find((s: any) => (b.ordinal ? `Score ${s.score}` : s.label) === l)?.value ?? 0])])) };
  }
  if (b.type === "treemap") return { columns: [{ key: "label", label: "Sector" }, { key: "display", label: "Scope 1+2", align: "right" }, { key: "share", label: "Share", align: "right" }], rows: b.items.map((d: any) => ({ label: d.label, display: d.display, share: d.share + "%" })) };
  return null;
}

function ChartCard({ b, i, children }: { b: Block; i: number; children: React.ReactNode }) {
  const [mode, setMode] = useState<"chart" | "table">("chart");
  const t = asTable(b);
  const tools = (
    <>
      {b.cite && <CiteChip refText={b.cite} />}
      {t && <button className={"tool" + (mode === "chart" ? " on" : "")} onClick={() => setMode("chart")}>Chart</button>}
      {t && <button className={"tool" + (mode === "table" ? " on" : "")} onClick={() => setMode("table")}>Table</button>}
      {t && <button className="tool" title="Download CSV" onClick={() => download(`${(b.title || "pramana").replace(/[^\w]+/g, "_")}.csv`, tableCsv(t))}><I.download style={{ width: 12, height: 12, verticalAlign: -2 }} /></button>}
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
    case "radar": return <Card title={b.title} delay={i * 70}><Radar b={b} /></Card>;
    case "position": return <Card title={b.title} subtitle={b.subtitle} delay={i * 70}><Position b={b} /></Card>;
    case "scoregrid": return <Card title={b.title} subtitle={b.subtitle} delay={i * 70}><ScoreGrid b={b} /></Card>;
    case "simulator": return <Card title={`What-if: ${b.metric}`} subtitle="Drag to explore. Other companies are held at their reported values." delay={i * 70}><Simulator b={b} /></Card>;
    case "rubric": return <Card title={`How Q${b.qid} is scored`} subtitle={b.question} delay={i * 70}><Rubric b={b} /></Card>;
    case "checklist": return <Card title={b.title} delay={i * 70}><Checklist b={b} /></Card>;
    case "quotes": return <Card title={b.title || "Disclosure"} subtitle="Verbatim from the filing. Highlights mark the most specific sentences." delay={i * 70}><Quotes b={b} /></Card>;
    case "report_quotes": return <Card title={b.title || "From the report"} delay={i * 70}><ReportQuotes b={b} /></Card>;
    case "insights": return <Card title="Ten signals from the E1 chapter" subtitle="IIMB report, Key Insights table" delay={i * 70}><Insights b={b} /></Card>;
    case "table": return (
      <Card title={b.title} delay={i * 70} tools={<button className="tool" onClick={() => download(`${(b.title || "table").replace(/[^\w]+/g, "_")}.csv`, tableCsv(b))}>CSV</button>}>
        <Table b={b} />
      </Card>
    );
    case "compare": return <Card title={b.title} delay={i * 70}><Compare b={b} /></Card>;
    case "matrix": return <Card title={b.title} delay={i * 70}><Matrix b={b} /></Card>;
    case "gap": return <Card title="Gap to top-rated peers" subtitle={`Q${b.qid} ${b.question}`} delay={i * 70}><Gap b={b} /></Card>;
    case "choices": return <Choices b={b} />;
    case "capabilities": return <Capabilities b={b} />;
    case "links": return <Card title={b.title} delay={i * 70}><Links b={b} /></Card>;
    case "callout": return <Callout b={b} />;
    default: return null;
  }
}
