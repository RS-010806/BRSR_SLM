import type { SVGProps } from "react";

const base = { fill: "none", stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round", strokeLinejoin: "round" } as const;
type P = SVGProps<SVGSVGElement>;

export const I = {
  plus: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M12 5v14M5 12h14" /></svg>),
  send: (p: P) => (<svg viewBox="0 0 24 24" {...base} strokeWidth={2} {...p}><path d="M12 19V5M5 12l7-7 7 7" /></svg>),
  chat: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M4 5h16v11H9l-5 4z" /></svg>),
  building: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M4 20V6l8-3v17M12 20V9l8 3v8M2 20h20M7 8h2M7 12h2M7 16h2M15 14h2M15 17h2" /></svg>),
  grid: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg>),
  book: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM4 5v16M9 7h6" /></svg>),
  sun: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>),
  moon: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z" /></svg>),
  menu: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M4 7h16M4 12h16M4 17h10" /></svg>),
  x: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M6 6l12 12M18 6L6 18" /></svg>),
  arrow: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M5 12h14M13 6l6 6-6 6" /></svg>),
  corner: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M9 14l-4-4 4-4M5 10h9a5 5 0 0 1 5 5v3" /></svg>),
  copy: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 0 1 2-2h8" /></svg>),
  link: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></svg>),
  print: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M7 9V3h10v6M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2M7 14h10v7H7z" /></svg>),
  eye: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></svg>),
  check: (p: P) => (<svg viewBox="0 0 24 24" {...base} strokeWidth={2.4} {...p}><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>),
  minus: (p: P) => (<svg viewBox="0 0 24 24" {...base} strokeWidth={2.4} {...p}><path d="M6 12h12" /></svg>),
  alert: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M12 3l10 18H2zM12 10v4M12 17.5v.5" /></svg>),
  info: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.5" /></svg>),
  shield: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" /><path d="M8.5 12l2.5 2.5 4.5-5" /></svg>),
  up: (p: P) => (<svg viewBox="0 0 24 24" {...base} strokeWidth={2.2} {...p}><path d="M7 14l5-5 5 5" /></svg>),
  down: (p: P) => (<svg viewBox="0 0 24 24" {...base} strokeWidth={2.2} {...p}><path d="M7 10l5 5 5-5" /></svg>),
  search: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><circle cx="11" cy="11" r="6.5" /><path d="M20 20l-4-4" /></svg>),
  target: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3.5" /></svg>),
  ext: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></svg>),
  download: (p: P) => (<svg viewBox="0 0 24 24" {...base} {...p}><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></svg>),
};

export function Mark({ size = 30 }: { size?: number }) {
  return (
    <svg className="brand-mark" width={size} height={size} viewBox="0 0 64 64" aria-hidden>
      <rect width="64" height="64" rx="15" fill="var(--brand)" />
      <path d="M21 46V18h13c6.2 0 10.2 3.7 10.2 9.2S40.2 36.6 34 36.6h-6.6" fill="none" stroke="var(--page)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="44" cy="46" r="4.2" fill="var(--focus)" />
    </svg>
  );
}
