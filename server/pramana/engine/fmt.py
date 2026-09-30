"""Number and text formatting. Deterministic, locale-independent."""
from __future__ import annotations

import re

MINUS = "−"
CO2 = "tCO₂e"
LEGAL_TAIL = re.compile(r"(\s+(limited|ltd\.?|company limited|corporation limited))+\s*$", re.I)


def short_name(name: str) -> str:
    s = LEGAL_TAIL.sub("", name).strip()
    return s or name


def num(v: float | None, digits: int = 2) -> str:
    """Full precision with thousands separators, trimmed decimals."""
    if v is None:
        return "not reported"
    if v == 0:
        return "0"
    a = abs(v)
    if a >= 1000:
        s = f"{v:,.0f}"
    elif a >= 1:
        s = f"{v:,.{digits}f}".rstrip("0").rstrip(".")
    elif a >= 0.001:
        s = f"{v:.4f}".rstrip("0").rstrip(".")
    else:
        s = f"{v:.3g}"
    return s.replace("-", MINUS)


def compact(v: float | None) -> str:
    """1.31 billion, 32.9 million, 845.2 thousand. Used in prose and tiles."""
    if v is None:
        return "n/a"
    a = abs(v)
    sign = MINUS if v < 0 else ""
    if a >= 1e9:
        return f"{sign}{a / 1e9:.2f} billion"
    if a >= 1e6:
        return f"{sign}{a / 1e6:.1f} million"
    if a >= 1e4:
        return f"{sign}{a:,.0f}"
    return num(v)


def tile(v: float | None) -> str:
    if v is None:
        return "n/a"
    a = abs(v)
    sign = MINUS if v < 0 else ""
    if a >= 1e9:
        return f"{sign}{a / 1e9:.2f}B"
    if a >= 1e6:
        return f"{sign}{a / 1e6:.2f}M"
    if a >= 1e4:
        return f"{sign}{a / 1e3:.1f}K"
    return num(v)


def pct(v: float | None, signed: bool = True, digits: int = 1) -> str:
    if v is None:
        return "n/a"
    s = f"{abs(v):.{digits}f}%"
    if not signed:
        return s if v >= 0 else MINUS + s
    if round(v, digits) == 0:
        return f"{0:.{digits}f}%"
    return ("+" if v > 0 else MINUS) + s


def share(a: int, b: int, digits: int = 1) -> str:
    return f"{(100.0 * a / b):.{digits}f}%" if b else "n/a"


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def plural(n: int, word: str, plural_word: str | None = None) -> str:
    return f"{n:,} {word if n == 1 else (plural_word or word + 's')}"


def join(items: list[str], conj: str = "and") -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" {conj} " + items[-1]


_KEEP_CASE = {"Scope", "GHG", "E1", "NGRBC", "BRSR", "SBTi", "Board", "PPP", "ISO"}


def lc(label: str) -> str:
    """Lower-case a label for use mid-sentence, keeping acronyms and 'Scope'."""
    if not label:
        return label
    first = label.split(" ", 1)[0]
    if first in _KEEP_CASE or first.isupper():
        return label
    return label[0].lower() + label[1:]
