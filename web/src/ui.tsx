import { createContext, Fragment, useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { Citation } from "./api";

export type AnswerCtxT = {
  citations: Citation[];
  openCite: (id: number) => void;
  activeCite: number | null;
  ask: (q: string) => void;
  prefetch?: (q: string) => void;
};
export const AnswerCtx = createContext<AnswerCtxT>({ citations: [], openCite: () => {}, activeCite: null, ask: () => {} });

/* Hover intent: prefetch after a short dwell so drive-by mouse movement costs nothing. */
export function useHoverPrefetch() {
  const { prefetch } = useAnswer();
  const t = useRef<number | undefined>(undefined);
  return (q: string) => ({
    onMouseEnter: () => { window.clearTimeout(t.current); t.current = window.setTimeout(() => prefetch?.(q), 90); },
    onMouseLeave: () => window.clearTimeout(t.current),
    onFocus: () => prefetch?.(q),
  });
}
export const useAnswer = () => useContext(AnswerCtx);

/* --------------------------------------------------------------- rich text */
const TOKEN = /(\*\*[^*]+\*\*|\[\d+\])/g;

export function Rich({ text }: { text: string }) {
  const { openCite, activeCite } = useAnswer();
  const parts = text.split(TOKEN).filter(Boolean);
  const isCite = (x: string) => /^\[\d+\]$/.test(x);
  const isBold = (x: string) => x.startsWith("**") && x.endsWith("**");
  const chip = (n: number, k: number | string) => (
    <button key={k} className={"cite" + (activeCite === n ? " on" : "")} onClick={() => openCite(n)} aria-label={`Source ${n}`}>{n}</button>
  );
  // Citation chips never wrap alone: each run of chips is glued to the word
  // before it and to any punctuation right after it.
  const out: ReactNode[] = [];
  for (let i = 0; i < parts.length; i++) {
    const p = parts[i];
    const cites: number[] = [];
    let j = isCite(p) ? i : i + 1;
    while (j < parts.length && isCite(parts[j])) cites.push(Number(parts[j++].slice(1, -1)));
    if (!cites.length) {
      out.push(isBold(p) ? <strong key={i}><Rich text={p.slice(2, -2)} /></strong> : <Fragment key={i}>{p}</Fragment>);
      continue;
    }
    let tail: ReactNode = null;
    if (!isCite(p)) {
      if (isBold(p)) tail = <strong><Rich text={p.slice(2, -2)} /></strong>;
      else {
        const cut = p.search(/\S+\s*$/);
        if (cut > 0) out.push(<Fragment key={"p" + i}>{p.slice(0, cut)}</Fragment>);
        tail = cut >= 0 ? p.slice(cut) : p;
      }
    }
    let punct = "";
    if (j < parts.length && /^[.,;:)]/.test(parts[j])) {
      punct = parts[j][0];
      parts[j] = parts[j].slice(1);
    }
    out.push(
      <span key={"g" + i} style={{ whiteSpace: "nowrap" }}>
        {tail}{cites.map((n, k) => chip(n, k))}{punct}
      </span>,
    );
    i = j - 1;
  }
  return <>{out}</>;
}

export function CiteChip({ refText }: { refText?: string | null }) {
  if (!refText) return null;
  return <Rich text={refText} />;
}

/* --------------------------------------------------------------- tooltip */
export type Tip = { x: number; y: number; title: string; lines?: string[] } | null;

export function useTip() {
  const [tip, setTip] = useState<Tip>(null);
  const node = tip ? (
    <div className="tip" style={{ left: tip.x, top: tip.y }} role="tooltip">
      <b>{tip.title}</b>
      {tip.lines?.map((l, i) => <div key={i}><span>{l}</span></div>)}
    </div>
  ) : null;
  const show = (e: React.MouseEvent | React.FocusEvent, title: string, lines?: string[]) => {
    const r = (e.currentTarget as Element).getBoundingClientRect();
    const x = "clientX" in e && e.clientX ? e.clientX : r.left + r.width / 2;
    const y = "clientY" in e && e.clientY ? e.clientY : r.top;
    setTip({ x, y, title, lines });
  };
  return { tip: node, show, hide: () => setTip(null) };
}

/* --------------------------------------------------------------- width */
export function useWidth<T extends HTMLElement>(initial = 640): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(initial);
  useLayoutEffect(() => {
    if (!ref.current) return;
    setW(ref.current.clientWidth || initial);
    const ro = new ResizeObserver((es) => {
      for (const e of es) setW(Math.max(260, Math.floor(e.contentRect.width)));
    });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

/* --------------------------------------------------------------- count up */
export function useCountUp(target: string, ms = 700): string {
  const m = target.match(/^([^\d−-]*)([−-]?[\d,]*\.?\d+)(.*)$/);
  const [v, setV] = useState(m ? target.replace(m[2], "0") : target);
  useEffect(() => {
    if (!m) {
      setV(target);
      return;
    }
    const neg = m[2].startsWith("−") || m[2].startsWith("-");
    const clean = m[2].replace(/[−,-]/g, "");
    const end = parseFloat(clean);
    const dec = (clean.split(".")[1] || "").length;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !isFinite(end)) {
      setV(target);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / ms);
      const e = 1 - Math.pow(1 - k, 3);
      const cur = end * e;
      const s = cur.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
      setV(m[1] + (neg ? "−" : "") + s + m[3]);
      if (k < 1) raf = requestAnimationFrame(tick);
      else setV(target);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return v;
}

/* --------------------------------------------------------------- formatting */
export function compact(v: number): string {
  const a = Math.abs(v);
  const s = v < 0 ? "−" : "";
  if (a >= 1e9) return s + (a / 1e9).toFixed(a >= 1e10 ? 0 : 1) + "B";
  if (a >= 1e6) return s + (a / 1e6).toFixed(a >= 1e7 ? 0 : 1) + "M";
  if (a >= 1e3) return s + (a / 1e3).toFixed(a >= 1e4 ? 0 : 1) + "K";
  if (a >= 1) return s + a.toFixed(a >= 10 ? 0 : 1);
  if (a === 0) return "0";
  return s + a.toPrecision(1);
}

export function Card({ title, subtitle, tools, children, delay = 0 }: { title?: string; subtitle?: string; tools?: ReactNode; children: ReactNode; delay?: number }) {
  return (
    <section className="card" style={{ animationDelay: `${delay}ms` }}>
      {(title || tools) && (
        <div className="card-h">
          <div>
            {title && <div className="card-t">{title}</div>}
            {subtitle && <div className="card-s">{subtitle}</div>}
          </div>
          {tools && <div className="card-tools">{tools}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function toast(msg: string) {
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2200);
}
