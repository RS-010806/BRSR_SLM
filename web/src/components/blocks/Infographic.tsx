import { useEffect, useRef, useState } from "react";
import { I } from "../../icons";
import { toast, useTheme } from "../../ui";
import { safeName, saveBlob } from "../../xlsx";

/* A one-page, post-style infographic drawn on a canvas at 1080 x 1350 (4:5),
   so what is on screen is exactly what downloads as an image. The picture is
   a pure function of the data and the theme: same answer, same image. */

type Pal = {
  bg: string; card: string; soft: string; ink: string; ink2: string; ink3: string; line: string; accent: string;
  brand: string; onBrand: string; scope: string[]; good: string; bad: string; goodBg: string; badBg: string; track: string;
};
const LIGHT: Pal = {
  bg: "#f6f5f1", card: "#fcfcfb", soft: "#efede7", ink: "#121212", ink2: "#4f4e49", ink3: "#6a6862", line: "#dcd9cf",
  accent: "#1c5cab", brand: "#14213d", onBrand: "#ffffff", scope: ["#2a78d6", "#eb6834", "#1baf7a"],
  good: "#006300", bad: "#b3261e", goodBg: "#e3f1e3", badBg: "#f9e4e2", track: "#e3e0d7",
};
const DARK: Pal = {
  bg: "#0f0f0e", card: "#1a1a19", soft: "#211f1e", ink: "#f4f3ee", ink2: "#c3c2b7", ink3: "#9a988f", line: "#33322f",
  accent: "#5fa8ff", brand: "#e8eefb", onBrand: "#0f0f0e", scope: ["#3987e5", "#d95926", "#199e70"],
  good: "#52c552", bad: "#f08a86", goodBg: "#13241a", badBg: "#2d1817", track: "#2a2927",
};

const W = 1080, H = 1350, M = 72;
const SANS = '"IBM Plex Sans", system-ui, sans-serif';
const MONO = '"IBM Plex Mono", ui-monospace, monospace';
const SERIF = '"Newsreader", Georgia, serif';

function rr(c: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  const k = Math.min(r, w / 2, h / 2);
  c.beginPath();
  c.moveTo(x + k, y);
  c.arcTo(x + w, y, x + w, y + h, k);
  c.arcTo(x + w, y + h, x, y + h, k);
  c.arcTo(x, y + h, x, y, k);
  c.arcTo(x, y, x + w, y, k);
  c.closePath();
}
function text(c: CanvasRenderingContext2D, s: string, x: number, y: number, font: string, color: string, align: CanvasTextAlign = "left") {
  c.font = font;
  c.fillStyle = color;
  c.textAlign = align;
  c.textBaseline = "alphabetic";
  c.fillText(s, x, y);
  return c.measureText(s).width;
}
function fit(c: CanvasRenderingContext2D, s: string, maxW: number, weight: string, family: string, from: number, to: number) {
  for (let size = from; size >= to; size -= 2) {
    c.font = `${weight} ${size}px ${family}`;
    if (c.measureText(s).width <= maxW) return size;
  }
  return to;
}
function wrap(c: CanvasRenderingContext2D, s: string, maxW: number, font: string, maxLines: number): string[] {
  c.font = font;
  const words = s.split(/\s+/);
  const lines: string[] = [];
  let cur = "";
  for (const w of words) {
    const next = cur ? cur + " " + w : w;
    if (c.measureText(next).width <= maxW || !cur) cur = next;
    else {
      lines.push(cur);
      cur = w;
    }
  }
  if (cur) lines.push(cur);
  if (lines.length > maxLines) {
    const cut = lines.slice(0, maxLines);
    let last = cut[maxLines - 1];
    while (last.length > 3 && c.measureText(last + "…").width > maxW) last = last.slice(0, -1);
    cut[maxLines - 1] = last.replace(/[\s,;:]+$/, "") + "…";
    return cut;
  }
  return lines;
}
function ellipsis(c: CanvasRenderingContext2D, s: string, maxW: number, font: string) {
  c.font = font;
  if (c.measureText(s).width <= maxW) return s;
  let t = s;
  while (t.length > 3 && c.measureText(t + "…").width > maxW) t = t.slice(0, -1);
  return t.trimEnd() + "…";
}
function pill(c: CanvasRenderingContext2D, s: string, xRight: number, yMid: number, font: string, fg: string, bg: string) {
  c.font = font;
  const w = c.measureText(s).width + 32, h = 40;
  rr(c, xRight - w, yMid - h / 2, w, h, 20);
  c.fillStyle = bg;
  c.fill();
  text(c, s, xRight - w / 2, yMid + 7, font, fg, "center");
  return w;
}
function tone(p: Pal, d: any): [string, string] {
  if (!d || d.tone === "neutral") return [p.ink2, p.soft];
  return d.tone === "good" ? [p.good, p.goodBg] : [p.bad, p.badBg];
}

function draw(cv: HTMLCanvasElement, b: any, p: Pal) {
  const c = cv.getContext("2d")!;
  c.clearRect(0, 0, W, H);
  c.fillStyle = p.bg;
  c.fillRect(0, 0, W, H);
  const CW = W - 2 * M;

  // brand row
  rr(c, M, 60, 46, 46, 12);
  c.fillStyle = p.brand;
  c.fill();
  text(c, "P", M + 23, 95, `600 30px ${SERIF}`, p.onBrand, "center");
  text(c, "Pramana", M + 60, 94, `500 30px ${SERIF}`, p.ink);
  pill(c, b.period, W - M, 83, `600 19px ${MONO}`, p.ink2, p.soft);

  // title
  let y = 178;
  text(c, String(b.eyebrow || "").toUpperCase(), M, y, `600 19px ${MONO}`, p.accent);
  const size = fit(c, b.title, CW, "500", SERIF, 78, 50);
  const tl = wrap(c, b.title, CW, `500 ${size}px ${SERIF}`, 2);
  y += 18;
  tl.forEach((ln) => {
    y += size * 1.04;
    text(c, ln, M, y, `500 ${size}px ${SERIF}`, p.ink);
  });
  y += 42;
  text(c, b.subtitle || "", M, y, `400 26px ${SANS}`, p.ink2);
  y += 34;

  // hero
  const hh = 214;
  rr(c, M, y, CW, hh, 26);
  c.fillStyle = p.card;
  c.fill();
  c.strokeStyle = p.line;
  c.lineWidth = 1.5;
  c.stroke();
  text(c, b.hero.label, M + 36, y + 54, `500 23px ${SANS}`, p.ink2);
  if (b.hero.delta) {
    const [fg, bg] = tone(p, b.hero.delta);
    pill(c, b.hero.delta.text, M + CW - 30, y + 46, `600 19px ${SANS}`, fg, bg);
  }
  const hs = fit(c, b.hero.value, CW - 72 - 330, "500", SERIF, 120, 70);
  const vw = text(c, b.hero.value, M + 36, y + 168, `500 ${hs}px ${SERIF}`, p.ink);
  text(c, b.hero.unit, M + 36 + vw + 18, y + 168, `500 29px ${SANS}`, p.ink2);
  y += hh + 20;

  // stats
  const stats: any[] = b.stats || [];
  if (stats.length) {
    const gap = 16, n = stats.length, bw = (CW - gap * (n - 1)) / n, bh = stats.some((s) => s.delta) ? 164 : 128;
    stats.forEach((s, i) => {
      const x = M + i * (bw + gap);
      rr(c, x, y, bw, bh, 20);
      c.fillStyle = p.card;
      c.fill();
      c.strokeStyle = p.line;
      c.stroke();
      text(c, ellipsis(c, s.label, bw - 40, `500 19px ${SANS}`), x + 20, y + 40, `500 19px ${SANS}`, p.ink3);
      const vs = fit(c, s.value, bw - 40, "600", SANS, 42, 24);
      text(c, s.value, x + 20, y + 92, `600 ${vs}px ${SANS}`, p.ink);
      if (s.unit) text(c, ellipsis(c, s.unit, bw - 40, `400 17px ${SANS}`), x + 20, y + 118, `400 17px ${SANS}`, p.ink3);
      if (s.delta) {
        const [fg] = tone(p, s.delta);
        text(c, ellipsis(c, s.delta.text, bw - 40, `600 16px ${SANS}`), x + 20, y + 146, `600 16px ${SANS}`, fg);
      }
    });
    y += bh + 32;
  }

  // split by scope
  const split: any[] = (b.split || []).filter((s: any) => s.value > 0);
  const total = split.reduce((a, s) => a + s.value, 0);
  if (split.length > 1 && total > 0) {
    text(c, "Emissions by scope", M, y, `600 22px ${SANS}`, p.ink);
    y += 20;
    const bh = 30, gap = 5;
    const avail = CW - gap * (split.length - 1);
    const ws = split.map((s) => Math.max(8, (s.value / total) * avail));
    const scale = avail / ws.reduce((a, w) => a + w, 0);
    let x = M;
    split.forEach((s, i) => {
      const w = ws[i] * scale;
      rr(c, x, y, w, bh, 8);
      c.fillStyle = p.scope[["Scope 1", "Scope 2", "Scope 3"].indexOf(s.label)] || p.scope[i % 3];
      c.fill();
      x += w + gap;
    });
    y += bh + 34;
    let lx = M;
    split.forEach((s, i) => {
      c.beginPath();
      c.arc(lx + 8, y - 7, 8, 0, Math.PI * 2);
      c.fillStyle = p.scope[["Scope 1", "Scope 2", "Scope 3"].indexOf(s.label)] || p.scope[i % 3];
      c.fill();
      const share = (100 * s.value) / total;
      const lab = `${s.label}  ${share >= 10 ? share.toFixed(0) : share >= 0.1 ? share.toFixed(1) : "<0.1"}%`;
      lx += 26 + text(c, lab, lx + 24, y, `500 20px ${SANS}`, p.ink2) + 34;
    });
    y += 44;
  }

  const footY = H - 92;

  if (b.kind === "company") {
    // disclosure checks, two per row
    const checks: any[] = b.checks || [];
    if (checks.length) {
      const colW = CW / 2;
      checks.forEach((k, i) => {
        const x = M + (i % 2) * colW, yy = y + Math.floor(i / 2) * 50;
        c.beginPath();
        c.arc(x + 15, yy + 2, 15, 0, Math.PI * 2);
        c.fillStyle = k.value ? p.accent : p.track;
        c.fill();
        c.strokeStyle = k.value ? p.bg : p.ink3;
        c.lineWidth = 3;
        c.lineCap = "round";
        c.lineJoin = "round";
        c.beginPath();
        if (k.value) {
          c.moveTo(x + 8, yy + 3);
          c.lineTo(x + 13, yy + 8);
          c.lineTo(x + 22, yy - 3);
        } else {
          c.moveTo(x + 9, yy + 2);
          c.lineTo(x + 21, yy + 2);
        }
        c.stroke();
        c.lineWidth = 1.5;
        text(c, ellipsis(c, k.label, colW - 60, `500 20px ${SANS}`), x + 42, yy + 9, `500 20px ${SANS}`, k.value ? p.ink : p.ink3);
      });
      y += Math.ceil(checks.length / 2) * 50 + 16;
    }
    // a sentence from the company's own disclosure
    const room = footY - 24 - y;
    if (b.quote?.text && room > 120) {
      const lines = wrap(c, `“${b.quote.text}”`, CW - 64, `italic 400 25px ${SERIF}`, Math.max(1, Math.floor((room - 78) / 34)));
      const qh = 70 + lines.length * 34;
      rr(c, M, y, CW, qh, 20);
      c.fillStyle = p.soft;
      c.fill();
      c.fillStyle = p.accent;
      rr(c, M, y, 6, qh, 3);
      c.fill();
      text(c, String(b.quote.label).toUpperCase(), M + 32, y + 38, `600 16px ${MONO}`, p.accent);
      lines.forEach((ln, i) => text(c, ln, M + 32, y + 74 + i * 34, `italic 400 25px ${SERIF}`, p.ink));
    }
  } else {
    // largest emitters
    const items: any[] = b.bars?.items || [];
    if (items.length) {
      text(c, b.bars.label, M, y, `600 22px ${SANS}`, p.ink);
      y += 18;
      const max = Math.max(...items.map((x) => x.value), 1);
      const labW = 300, valW = 120, barW = CW - labW - valW - 24;
      items.forEach((it) => {
        y += 34;
        text(c, ellipsis(c, it.label, labW - 12, `500 19px ${SANS}`), M, y, `500 19px ${SANS}`, p.ink2);
        rr(c, M + labW, y - 17, barW, 20, 6);
        c.fillStyle = p.track;
        c.fill();
        rr(c, M + labW, y - 17, Math.max(6, (it.value / max) * barW), 20, 6);
        c.fillStyle = p.scope[0];
        c.fill();
        text(c, it.display, W - M, y, `600 19px ${SANS}`, p.ink, "right");
      });
      y += 36;
    }
    // shares of companies
    const shares: any[] = b.shares || [];
    if (shares.length && footY - y > 130) {
      const gap = 16, bw = (CW - gap * (shares.length - 1)) / shares.length;
      shares.forEach((s, i) => {
        const x = M + i * (bw + gap);
        text(c, `${s.value.toFixed(0)}%`, x, y + 40, `600 40px ${SANS}`, p.ink);
        text(c, s.text + " companies", x, y + 68, `400 17px ${SANS}`, p.ink3);
        rr(c, x, y + 82, bw, 8, 4);
        c.fillStyle = p.track;
        c.fill();
        rr(c, x, y + 82, Math.max(8, (s.value / 100) * bw), 8, 4);
        c.fillStyle = p.accent;
        c.fill();
        const ll = wrap(c, s.label, bw, `500 18px ${SANS}`, 2);
        ll.forEach((ln, k) => text(c, ln, x, y + 116 + k * 24, `500 18px ${SANS}`, p.ink2));
      });
    }
  }

  // footer
  c.strokeStyle = p.line;
  c.lineWidth = 1.5;
  c.beginPath();
  c.moveTo(M, footY);
  c.lineTo(W - M, footY);
  c.stroke();
  text(c, b.source, M, footY + 40, `400 18px ${SANS}`, p.ink3);
  text(c, "Figures as disclosed", W - M, footY + 40, `400 18px ${SANS}`, p.ink3, "right");
}

export function Infographic({ b }: { b: any }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const theme = useTheme();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let live = true;
    const fonts = [`500 60px "Newsreader"`, `italic 400 25px "Newsreader"`, `600 19px "IBM Plex Mono"`, `400 20px "IBM Plex Sans"`,
      `500 20px "IBM Plex Sans"`, `600 20px "IBM Plex Sans"`];
    const paint = () => { if (live && ref.current) { draw(ref.current, b, theme === "dark" ? DARK : LIGHT); setReady(true); } };
    paint();   // draw at once with whatever fonts are available, then again when the real ones have loaded
    Promise.all(fonts.map((f) => document.fonts?.load(f).catch(() => null))).then(paint);
    return () => { live = false; };
  }, [b, theme]);

  const blob = () => new Promise<Blob | null>((res) => ref.current?.toBlob((x) => res(x), "image/png"));
  const download = async () => {
    const x = await blob();
    if (x) saveBlob(x, `${safeName(b.filename || b.title)}.png`);
  };
  const copy = async () => {
    try {
      const x = await blob();
      if (!x || !("ClipboardItem" in window)) throw new Error("unsupported");
      await navigator.clipboard.write([new ClipboardItem({ "image/png": x })]);
      toast("Image copied");
    } catch {
      toast("Copying images is not supported in this browser. Use Download instead.");
    }
  };
  const summary = `${b.title}. ${b.hero.label}: ${b.hero.value} ${b.hero.unit}. ${(b.stats || []).map((s: any) => `${s.label}: ${s.value} ${s.unit}`).join(". ")}.`;
  return (
    <div className="infographic">
      <canvas ref={ref} width={W} height={H} role="img" aria-label={`Infographic. ${summary}`} className={ready ? "ready" : ""} />
      <div className="info-actions">
        <button className="btn primary" onClick={download}><I.download />Download image</button>
        <button className="btn" onClick={copy}><I.copy />Copy image</button>
      </div>
    </div>
  );
}
