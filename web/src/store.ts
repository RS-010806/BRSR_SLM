import type { Answer, Ctx } from "./api";

/* Conversation memory lives only in this browser (localStorage). Nothing about
   the user is sent anywhere except the question and its conversation context. */

export type Msg =
  | { role: "user"; text: string; at: number }
  | { role: "assistant"; answer?: Answer; error?: string; q: string; at: number; pending?: boolean };

export type Thread = { id: string; title: string; createdAt: number; updatedAt: number; messages: Msg[]; context: Ctx };

const KEY = "pramana.threads.v3";
const LENS = "pramana.lens";
const THEME = "pramana.theme";

function safeGet(k: string): string | null {
  try {
    return localStorage.getItem(k);
  } catch {
    return null;
  }
}
function safeSet(k: string, v: string | null) {
  try {
    if (v === null) localStorage.removeItem(k);
    else localStorage.setItem(k, v);
  } catch {
    /* storage unavailable (private mode, blocked): memory is session-only */
  }
}

export function loadThreads(): Thread[] {
  const raw = safeGet(KEY);
  if (!raw) return [];
  try {
    const t = JSON.parse(raw) as Thread[];
    return Array.isArray(t) ? t.map((x) => ({ ...x, messages: x.messages.filter((m) => !(m.role === "assistant" && m.pending)) })) : [];
  } catch {
    return [];
  }
}

export function saveThreads(ts: Thread[]) {
  // keep the most recent 80 conversations to stay within the storage quota
  const slim = ts
    .slice(0, 80)
    .map((t) => ({
      ...t,
      messages: t.messages
        .filter((m) => !(m.role === "assistant" && m.pending))
        .map((m) => m),
    }));
  let payload = JSON.stringify(slim);
  if (payload.length > 4_000_000) {
    payload = JSON.stringify(slim.slice(0, 20));
  }
  safeSet(KEY, payload);
}

export function newId(): string {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
}

export function getLens(): string | null {
  return safeGet(LENS);
}
export function setLens(id: string | null) {
  safeSet(LENS, id);
}

export type Theme = "light" | "dark" | "system";
export function getTheme(): Theme {
  const t = safeGet(THEME);
  return t === "light" || t === "dark" ? t : "system";
}
export function setTheme(t: Theme) {
  safeSet(THEME, t === "system" ? null : t);
  if (t === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = t;
}
