export type Ctx = {
  intent?: string | null;
  companies?: string[];
  sector?: string | null;
  metric?: string | null;
  tech?: string[];
  lens?: string | null;
};

export type Citation = {
  id: number;
  kind: "cell" | "rating" | "report_table" | "report_text" | "derived" | "method";
  [k: string]: any;
};

export type Block = { type: string; [k: string]: any };

export type Answer = {
  status: "answered" | "partial" | "not_found" | "out_of_scope" | "clarify";
  kicker: string;
  title: string;
  lead: string[];
  blocks: Block[];
  citations: Citation[];
  followups: string[];
  notes: { kind: string; text: string }[];
  entities: { id: string; name: string; short: string; sector: string; sector_id: string }[];
  fingerprint: string;
  context: Ctx;
  trace: any;
};

export type Company = { id: string; name: string; short: string; sector: string; sector_name: string };

export type Meta = {
  name: string;
  dataset: any;
  sectors: { id: string; name: string; short: string; nse_code: string; n: number }[];
  questions: any[];
  reconciliation: { total: number; matched: number; by_table: Record<string, { checks: number; matched: number }>; ai_scored_divergence: any };
  model: any;
  eval: any;
  flags: { report_exclusions: number; unit_checks: number; magnitude_checks: number };
};

export async function ask(q: string, context?: Ctx): Promise<Answer> {
  const r = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q, context: context || null }),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(r.status === 429 ? "Too many requests. Please wait a moment." : t || `HTTP ${r.status}`);
  }
  return r.json();
}

let _companies: Promise<Company[]> | null = null;
export function companies(): Promise<Company[]> {
  if (!_companies) _companies = fetch("/api/companies").then((r) => r.json());
  return _companies;
}

let _meta: Promise<Meta> | null = null;
export function meta(): Promise<Meta> {
  if (!_meta) _meta = fetch("/api/meta").then((r) => r.json());
  return _meta;
}
