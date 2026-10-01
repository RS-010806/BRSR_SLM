export type Prefs = { peers?: string[]; emissions?: string; n?: number; aliases?: Record<string, string> };

export type Ctx = {
  intent?: string | null;
  companies?: string[];
  sector?: string | null;
  metric?: string | null;
  tech?: string[];
  lens?: string | null;
  prefs?: Prefs | null;
  pending?: { text: string; ids: string[] } | null;
};

export type Citation = {
  id: number;
  kind: "filing" | "computed" | "note";
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
};

export type Company = { id: string; name: string; short: string; sector: string; sector_name: string };

export type Meta = {
  name: string;
  companies: number;
  period: string;
  sectors: { id: string; name: string; short: string; n: number }[];
};

/* ---------------------------------------------------------------- answer cache
   Answers are a pure function of (question, context), so a cache can never be
   stale. Prefetched answers land here too. */
const cache = new Map<string, Promise<Answer>>();
const keyOf = (q: string, ctx?: Ctx) => JSON.stringify([q.trim(), cleanCtx(ctx)]);

function cleanCtx(ctx?: Ctx): Ctx {
  const out: any = {};
  for (const [k, v] of Object.entries(ctx || {})) {
    if (v === null || v === undefined) continue;
    if (Array.isArray(v) && !v.length) continue;
    if (typeof v === "object" && !Array.isArray(v) && !Object.keys(v).length) continue;
    out[k] = v;
  }
  return out;
}

async function fetchAnswer(q: string, context: Ctx, prefetch: boolean): Promise<Answer> {
  const r = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(prefetch ? { "X-Pramana-Prefetch": "1" } : {}) },
    body: JSON.stringify({ q, context }),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(r.status === 429 ? "Too many requests. Please wait a moment." : t || `HTTP ${r.status}`);
  }
  return r.json();
}

export function ask(q: string, context?: Ctx): Promise<Answer> {
  const ctx = cleanCtx(context);
  const k = keyOf(q, ctx);
  const hit = cache.get(k);
  if (hit) return hit;
  const p = fetchAnswer(q, ctx, false);
  cache.set(k, p);
  p.catch(() => cache.delete(k));
  return p;
}

export function prefetch(q: string, context?: Ctx) {
  const ctx = cleanCtx(context);
  const k = keyOf(q, ctx);
  if (cache.has(k) || cache.size > 300) return;
  const p = fetchAnswer(q, ctx, true);
  cache.set(k, p);
  p.catch(() => cache.delete(k));
}

export async function sendFeedback(a: Answer, q: string, rating: 1 | -1, note?: string) {
  await fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fingerprint: a.fingerprint, q, rating, note: note || null }),
  });
}

export async function createShare(q: string, context: Ctx | undefined, fingerprint: string): Promise<string | null> {
  try {
    const r = await fetch("/api/share", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q, context: cleanCtx(context), fingerprint }),
    });
    if (!r.ok) return null;
    const j = await r.json();
    return `${window.location.origin}${j.path}`;
  } catch {
    return null;
  }
}

export async function resolveShare(code: string): Promise<{ q: string; ctx: Ctx } | null> {
  try {
    const r = await fetch(`/api/share/${encodeURIComponent(code)}`);
    return r.ok ? r.json() : null;
  } catch {
    return null;
  }
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
