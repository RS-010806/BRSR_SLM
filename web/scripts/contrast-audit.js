/*
 * Contrast audit: measures WCAG contrast of every visible text element against
 * the colour actually rendered behind it (HTML backgrounds, SVG fills, opacity).
 *
 * Run inside the page (Playwright page.evaluate). Returns the failing elements.
 *   FAIL  < 3.0:1 for any text (hard to read or invisible)
 *   WARN  < 4.5:1 for text smaller than 18.66px bold / 24px regular
 */
window.__contrastAudit = () => {
  const cv = document.createElement("canvas");
  cv.width = cv.height = 1;
  const cx = cv.getContext("2d", { willReadFrequently: true });
  // Resolve any CSS colour (rgb, oklab, color-mix output...) to sRGB via the canvas.
  const rgba = (css) => {
    if (!css || css === "none" || css === "transparent") return [0, 0, 0, 0];
    cx.clearRect(0, 0, 1, 1);
    cx.fillStyle = "rgba(0,0,0,0)";
    cx.fillStyle = css;
    cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  };
  const over = (top, under) => {
    const a = top[3];
    return [top[0] * a + under[0] * (1 - a), top[1] * a + under[1] * (1 - a), top[2] * a + under[2] * (1 - a), 1];
  };
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };

  const pageBg = rgba(getComputedStyle(document.body).backgroundColor);
  const htmlBg = (el) => {
    const stack = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const cs = getComputedStyle(n);
      const c = rgba(cs.backgroundColor);
      if (c[3] > 0) stack.push([c[0], c[1], c[2], c[3] * parseFloat(cs.opacity || "1")]);
      if (c[3] >= 1) break;
    }
    let col = pageBg[3] ? pageBg : [255, 255, 255, 1];
    for (let i = stack.length - 1; i >= 0; i--) col = over(stack[i], col);
    return col;
  };
  const svgUnder = (textEl) => {
    const r = textEl.getBoundingClientRect();
    const px = r.left + r.width / 2, py = r.top + r.height / 2;
    const els = document.elementsFromPoint(px, py);
    const shapes = [];
    for (const e of els) {
      if (e === textEl || e.tagName === "text" || e.tagName === "tspan") continue;
      if (!(e instanceof SVGElement)) break;
      if (!["rect", "path", "circle", "polygon", "ellipse"].includes(e.tagName)) continue;
      const cs = getComputedStyle(e);
      const c = rgba(cs.fill);
      const op = parseFloat(cs.fillOpacity || "1") * parseFloat(cs.opacity || "1");
      if (c[3] * op > 0.02) shapes.push([c[0], c[1], c[2], c[3] * op]);
      if (c[3] * op >= 0.99) break;
    }
    const svg = textEl.ownerSVGElement;
    let col = htmlBg(svg || textEl.parentElement);
    for (let i = shapes.length - 1; i >= 0; i--) col = over(shapes[i], col);
    return col;
  };

  const out = [];
  const seen = new Set();
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const cs = getComputedStyle(el);
    return cs.visibility !== "hidden" && cs.display !== "none" && parseFloat(cs.opacity) > 0.05;
  };
  // HTML elements that own a non-empty text node
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let t = walker.nextNode(); t; t = walker.nextNode()) {
    if (!t.textContent.trim()) continue;
    const el = t.parentElement;
    if (!el || seen.has(el) || el.closest("svg") || el.closest("script,style,noscript")) continue;
    seen.add(el);
    if (!visible(el)) continue;
    const cs = getComputedStyle(el);
    const fg = rgba(cs.color);
    if (fg[3] === 0) continue;
    const bg = htmlBg(el);
    const eff = over([fg[0], fg[1], fg[2], fg[3] * parseFloat(cs.opacity || "1")], bg);
    const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight) >= 600;
    const large = size >= 24 || (bold && size >= 18.66);
    const cr = ratio(eff, bg);
    if (cr < (large ? 3 : 4.5)) out.push({ level: cr < 3 ? "FAIL" : "WARN", ratio: +cr.toFixed(2), text: t.textContent.trim().slice(0, 40), where: el.className?.toString?.().slice(0, 40) || el.tagName, size });
  }
  // SVG text
  for (const el of document.querySelectorAll("svg text")) {
    if (!el.textContent.trim() || !visible(el)) continue;
    const cs = getComputedStyle(el);
    const fg = rgba(cs.fill);
    if (fg[3] === 0) continue;
    const bg = svgUnder(el);
    const cr = ratio(fg, bg);
    const size = parseFloat(cs.fontSize);
    if (cr < 4.5) out.push({ level: cr < 3 ? "FAIL" : "WARN", ratio: +cr.toFixed(2), text: el.textContent.trim().slice(0, 40), where: "svg:" + (el.getAttribute("class") || ""), size });
  }
  return out;
};
