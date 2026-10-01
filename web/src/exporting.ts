import type { Answer, Block } from "./api";
import { downloadXlsx, type Cell, type Sheet } from "./xlsx";

export const SOURCE_NOTE = "Source: company BRSR disclosures, FY 2024-25 (FY 2023-24 for comparison). Figures are as disclosed.";

const plain = (s: string) => s.replace(/\*\*/g, "").replace(/\s*\[\d+\]/g, "").replace(/\s+([.,;:])/g, "$1").trim();
const asNumber = (s: any): Cell => {
  if (typeof s !== "string") return s;
  const t = s.replace(/−/g, "-").replace(/,/g, "");
  return /^-?\d*\.?\d+$/.test(t) ? Number(t) : s;
};

/* A table or chart as a sheet: plain headers with units, raw numbers in the cells. */
export function blockSheet(b: Block): Sheet | null {
  const x = b.export;
  if (!x || !x.columns?.length) return null;
  return { name: x.title || b.title || "Data", title: x.title || b.title, note: x.note || SOURCE_NOTE, columns: x.columns, rows: x.rows };
}

export function downloadBlock(b: Block) {
  const s = blockSheet(b);
  if (s) downloadXlsx(s.title || "Pramana data", [s]);
}

/* The whole answer as a workbook: the answer in words, every cited figure, then each table. */
export function answerSheets(a: Answer, q: string): Sheet[] {
  const rows: Cell[][] = [["Question", q], ["Answer", a.lead.map(plain).join(" ")]];
  a.blocks.filter((b) => b.type === "points").forEach((b) => b.items.forEach((t: string) => rows.push(["", plain(t)])));
  a.notes.forEach((n) => rows.push(["Note", n.text]));
  const sheets: Sheet[] = [{ name: "Answer", title: a.title || "Answer", note: SOURCE_NOTE, columns: ["Item", "Detail"], rows }];
  const figs = a.citations.filter((c) => c.kind === "filing" && c.value != null);
  if (figs.length)
    sheets.push({
      name: "Figures", title: "Figures used in this answer", note: SOURCE_NOTE,
      columns: ["Company", "Disclosure item", "Financial year", "Value as disclosed"],
      rows: figs.map((c) => [c.company, c.item, c.fy, asNumber(c.value)]),
    });
  a.blocks.forEach((b) => {
    const s = blockSheet(b);
    if (s) sheets.push(s);
    if (b.type === "quotes")
      sheets.push({
        name: b.title || "Disclosures", title: b.title || "Disclosures, as written by the company", note: SOURCE_NOTE,
        columns: ["Company", "Sector", "Disclosure item", "Text as disclosed"],
        rows: b.items.map((it: any) => [it.company, it.sector, it.topic, it.text]),
      });
  });
  return sheets;
}

export function downloadAnswer(a: Answer, q: string) {
  downloadXlsx(a.title || "Pramana answer", answerSheets(a, q));
}
