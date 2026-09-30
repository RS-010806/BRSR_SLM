import { createContext, Fragment, useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { Citation } from "./api";

export type AnswerCtxT = {
  citations: Citation[];
  openCite: (id: number) => void;
  activeCite: number | null;
  ask: (q: string) => void;
};
export const AnswerCtx = createContext<AnswerCtxT>({ citations: [], openCite: () => {}, activeCite: null, ask: () => {} });
export const useAnswer = () => useContext(AnswerCtx);

/* --------------------------------------------------------------- rich text */
const TOKEN = /(\*\*[^*]+\*\*|\[\d+\])/g;

export function Rich({ text }: { text: string }) {
  const { openCite, activeCite } = useAnswer();
  const parts = text.split(TOKEN).filter(Boolean);
  // keep a chip together with the punctuation that follows it, so it never wraps alone
  const glue: string[] = [];
  for (let i = 0; i < parts.length; i++) {
    const nx = parts[i + 1];
    if (/^\[\d+\]$/.test(parts[i]) && nx && /^[.,;:)]/.test(nx)) {
      glue.push(parts[i] + "\u0000" + nx[0]);
      parts[i + 1] = nx.slice(1);
    } else glue.push(parts[i]);
  }
  return (
    <>
      {glue.filter(Boolean).map((p, i) => {
        const m = p.match(/^\[(\d+)\](?:\u0000(.))?$/);
        if (m) {
          const n = Number(m[1]);
          const chip = (
            <button className={"cite" + (activeCite === n ? " on" : "")} onClick={() => openCite(n)} aria-label={`Source ${n}`}>
              {n}
            </button>
          );
          return m[2] ? <span key={i} style={{ whiteSpace: "nowrap" }}>{chip}{m[2]}</span> : <Fragment key={i}>{chip}</Fragment>;
        }
        if (p.startsWith("**") && p.endsWith("**")) return <strong key={i}><Rich text={p.slice(2, -2)} /></strong>;
        return <Fragment key={i}>{p}</Fragment>;
      })}
    </>
  );
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
