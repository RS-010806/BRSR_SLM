"""Evidence extraction from narrative disclosures.

Everything here selects or counts spans of the original text; nothing is
paraphrased. Highlight offsets always index into the exact source cell.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

THEMES: dict[str, list[str]] = {
    "Renewable energy": [r"\bsolar\b", r"\bwind\b", r"\brenewable", r"\bre\s?100\b", r"\bpower purchase agreement",
                         r"\bppa\b", r"\bopen access\b", r"\bgreen power\b", r"\bhybrid\b.{0,20}\b(power|energy|plant)",
                         r"\bround[- ]the[- ]clock\b", r"\bhydro ?power\b", r"\brooftop\b"],
    "Energy efficiency": [r"\benergy[- ]efficien", r"\bled\b", r"\bvfds?\b", r"\bvariable frequency",
                          r"\benergy audit", r"\bheat pump", r"\bpat scheme\b", r"\bbee\b", r"\bprocess optimi[sz]"],
    "Waste heat recovery": [r"\bwaste heat\b", r"\bwhrs?\b", r"\bheat recovery\b"],
    "Fuel switching and alternative fuels": [r"\balternative fuel", r"\bbiomass\b", r"\bafr\b", r"\btsr\b",
                                              r"\brdf\b", r"\brefuse[- ]derived", r"\bfuel switch", r"\bcng\b",
                                              r"\blng\b", r"\bpng\b", r"\bnatural gas\b", r"\bbio[- ]?fuel",
                                              r"\bbiogas\b", r"\bcompressed biogas\b", r"\bcbg\b"],
    "Electrification and EVs": [r"\belectric vehicle", r"\bevs?\b", r"\be-?mobility\b", r"\belectric (bus|buses|fleet|forklift|boiler)",
                                r"\belectrifi"],
    "Green hydrogen": [r"\bgreen hydrogen\b", r"\bhydrogen\b"],
    "Carbon capture": [r"\bcarbon capture\b", r"\bccus\b", r"\bccs\b", r"\bsequestration\b"],
    "Science-based or net-zero targets": [r"\bsbti\b", r"\bscience[- ]based", r"\bnet[- ]?zero\b", r"\bcarbon neutral"],
    "Afforestation and carbon sinks": [r"\bafforestation\b", r"\bplantation", r"\btrees?\b", r"\bcarbon sink",
                                       r"\bmiyawaki\b"],
    "Green buildings": [r"\bgreen building", r"\bleed\b", r"\bigbc\b", r"\bgriha\b"],
    "Internal carbon pricing": [r"\binternal carbon pric", r"\bcarbon pric", r"\bshadow carbon"],
    "Logistics and transport optimisation": [r"\bmodal shift\b", r"\brail(way)? transport", r"\broute optimi[sz]",
                                             r"\blogistics optimi[sz]", r"\bfleet optimi[sz]"],
    "Low-carbon products and clinker substitution": [r"\bblended cement", r"\bclinker factor\b", r"\bclinker substitution",
                                                     r"\bfly ash\b", r"\bslag\b", r"\bgreen steel\b", r"\blow[- ]carbon"],
}
_THEME_RE = {t: re.compile("|".join(ps), re.I) for t, ps in THEMES.items()}

_QUANT = re.compile(r"\d[\d,]*(\.\d+)?\s*(%|percent|tco2e?|tco₂e|tonnes?|tons?|mt\b|mwp?\b|kwp?\b|gwh|mwh|kwh|gj\b|"
                    r"mw\b|kl\b|crore|lakh|units?)", re.I)
_YEAR = re.compile(r"\b(fy\s?)?20[2-5]\d\b", re.I)
_BASELINE = re.compile(r"\b(baseline|base year|by 20\d\d|reduction of|reduced by|reduce by|compared to|vs\.?|against)\b", re.I)


def themes_in(text: str) -> list[str]:
    return [t for t, r in _THEME_RE.items() if r.search(text or "")]


def theme_spans(text: str) -> dict[str, list[tuple[int, int]]]:
    out = {}
    for t, r in _THEME_RE.items():
        sp = [(m.start(), m.end()) for m in r.finditer(text or "")]
        if sp:
            out[t] = sp
    return out


def specificity(sentence: str) -> float:
    """How concrete a sentence is: quantities, years, baselines, named practices."""
    s = 0.0
    s += 2.0 * len(_QUANT.findall(sentence))
    s += 1.0 * len(_YEAR.findall(sentence))
    s += 1.0 * bool(_BASELINE.search(sentence))
    s += 0.75 * len(themes_in(sentence))
    s -= 0.004 * max(0, len(sentence) - 400)
    return round(s, 3)


def segments_for(corpus_index, cid: str, qid: str) -> list[dict]:
    return corpus_index.get((cid, qid), [])


def highlight(segs: list[dict], k: int = 3, min_score: float = 2.0) -> list[dict]:
    """Pick the k most specific sentences (ties broken by position)."""
    scored = [(specificity(s["text"]), s["seg"], s) for s in segs]
    top = sorted([x for x in scored if x[0] >= min_score], key=lambda x: (-x[0], x[1]))[:k]
    keep = {x[1] for x in top}
    return [{"start": s["start"], "end": s["end"], "score": sc, "highlight": s["seg"] in keep}
            for sc, _, s in sorted(scored, key=lambda x: x[1])]


# --------------------------------------------------------------------------- search

TOKEN = re.compile(r"[a-z0-9]+")


class DisclosureIndex:
    """BM25 over sentence segments of every narrative disclosure plus report text."""

    def __init__(self, corpus: list[dict]):
        self.docs = corpus
        self.by_cell: dict[tuple, list[dict]] = defaultdict(list)
        for d in corpus:
            if d["kind"] == "disclosure":
                self.by_cell[(d["cid"], d["qid"])].append(d)
        self.tf = []
        df = Counter()
        for d in corpus:
            toks = TOKEN.findall(d["text"].lower())
            c = Counter(toks)
            self.tf.append((c, len(toks)))
            df.update(c.keys())
        n = len(corpus)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.avgdl = sum(l for _, l in self.tf) / max(n, 1)

    def bm25(self, query: str, kinds: set[str], limit: int = 8, k1: float = 1.2, b: float = 0.75):
        q = [t for t in TOKEN.findall(query.lower()) if t in self.idf]
        if not q:
            return []
        out = []
        for i, d in enumerate(self.docs):
            if d["kind"] not in kinds:
                continue
            c, dl = self.tf[i]
            s = 0.0
            for t in q:
                f = c.get(t, 0)
                if f:
                    s += self.idf[t] * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / self.avgdl))
            if s > 0:
                out.append((round(s, 6), i))
        out.sort(key=lambda x: (-x[0], x[1]))
        return [(s, self.docs[i]) for s, i in out[:limit]]

    def phrase(self, patterns: list[str], qids: set[str], cids: set[str] | None = None):
        """Exact (regex) phrase search in disclosure segments. Returns {cid: [(doc, spans)]}."""
        rx = re.compile("|".join(patterns), re.I)
        hits: dict[str, list] = defaultdict(list)
        for d in self.docs:
            if d["kind"] != "disclosure" or d["qid"] not in qids:
                continue
            if cids is not None and d["cid"] not in cids:
                continue
            sp = [(m.start(), m.end()) for m in rx.finditer(d["text"])]
            if sp:
                hits[d["cid"]].append((d, sp))
        return hits
