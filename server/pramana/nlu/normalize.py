"""Text normalisation shared by training and inference.

Pipeline:  prep -> tokenize -> (entity linking) -> mask

The same functions run on synthetic training sentences and on live user
queries, so the model never sees a distribution shift caused by formatting.
Entity linking happens before number masking because some company names
contain digits (3M India, 360 ONE WAM, 63 moons technologies).
"""
from __future__ import annotations

import re
import unicodedata

CO, SEC, NUM, PCT, YEAR = "<co>", "<sec>", "<num>", "<pct>", "<year>"
SPECIALS = [CO, SEC, NUM, PCT, YEAR]

_PRE = [
    (r"[‘’‛`´]", "'"),
    (r"[“”]", '"'),
    (r"[–—−]", "-"),
    (r"'s\b", ""),
    (r"&", " and "),
    (r"\bco\s*2\s*e?\b", "co2"),
    (r"\bghgs\b", "ghg"),
    (r"\bscopes?\s*[-_]?\s*(?:1|one|i)\s*(?:\+|and|,|/)?\s*(?:scope\s*)?(?:2|two|ii)\s*(?:\+|and|,|/|,\s*and)?\s*(?:scope\s*)?(?:3|three|iii)\b", " scope12 scope3 "),
    (r"\ball\s+(?:the\s+)?(?:three\s+|3\s+)?scopes\b", " scope12 scope3 "),
    (r"\bscopes?\s*[-_]?\s*(?:1|one|i)\s*(?:\+|and|,|/)\s*(?:scope\s*)?(?:2|two|ii)\b", " scope12 "),
    (r"\bscope\s*[-_]?\s*(?:1|one|i)\b", " scope1 "),
    (r"\bscope\s*[-_]?\s*(?:2|two|ii)\b", " scope2 "),
    (r"\bscope\s*[-_]?\s*(?:3|three|iii)\b", " scope3 "),
    (r"\bprinciple\s*(?:6|vi|six)\b", " principle6 "),
    (r"\biso\s*[-:]?\s*(\d{4,5})(?::\d{4})?", r" iso\1 "),
    (r"\bnet[\s-]*zero\b", " netzero "),
    (r"\bfy\s*'?\s*\d{2,4}\s*[-/]\s*\d{2,4}\b", " <year> "),
    (r"\b(?:19|20)\d{2}\s*[-/]\s*\d{2,4}\b", " <year> "),
    (r"\bfy\s*'?\s*\d{2,4}\b", " <year> "),
    (r"(\d+(?:\.\d+)?)\s*(?:%|percent\b|per\s+cent\b|pct\b)", r" \1% "),
]
_PRE = [(re.compile(p, re.I), r) for p, r in _PRE]
_TOKEN = re.compile(r"<[a-z]+>|\d+(?:\.\d+)?%|\d+(?:\.\d+)?|[a-z0-9]+")


def prep(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).lower()
    for pat, rep in _PRE:
        t = pat.sub(rep, t)
    return t


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text)


def mask(toks: list[str]) -> tuple[list[str], list[float], list[float]]:
    """Replace numbers with <num>/<pct>/<year>; return captured values."""
    out, nums, pcts = [], [], []
    for t in toks:
        if t.startswith("<"):
            out.append(t)
        elif t.endswith("%"):
            pcts.append(float(t[:-1]))
            out.append(PCT)
        elif re.fullmatch(r"(?:19|20)\d{2}", t):
            out.append(YEAR)
        elif re.fullmatch(r"\d+(?:\.\d+)?", t):
            nums.append(float(t))
            out.append(NUM)
        else:
            out.append(t)
    return out, nums, pcts


def norm_name(name: str) -> list[str]:
    """Tokens for a company/sector name, using the exact same rules as queries."""
    return tokenize(prep(name))


def model_text(text_with_placeholders: str) -> str:
    """Training-side helper: template text (already containing <co>/<sec>) to model input."""
    toks, _, _ = mask(tokenize(prep(text_with_placeholders)))
    return " ".join(toks)
