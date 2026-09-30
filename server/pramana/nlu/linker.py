"""Deterministic entity linking over normalised query tokens.

A single longest-match pass over a token trie finds companies, companies we
know are absent from the dataset, sectors, metrics, out-of-scope topics and
technology keywords. Ties in span length are broken by entity priority.
Unmatched spans are then fuzzy-matched against company aliases (typo
tolerance) with a strict cutoff. The output is fully determined by the input.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein

from .lexicon import KNOWN_ABSENT, METRICS, OFFTOPIC, SECTOR_SYNONYMS, STOP
from .normalize import CO, SEC, norm_name, prep, tokenize

NUMERIC = re.compile(r"\d+(?:\.\d+)?%?")
PRIORITY = {"company": 6, "absent": 5, "sector": 4, "metric": 3, "tech": 2, "offtopic": 1}

# Technology and practice keywords people search disclosures for.
TECH_TERMS: dict[str, list[str]] = {
    "solar": ["solar", "rooftop solar", "solar power", "solar plant", "solar energy", "solar pv"],
    "wind": ["wind", "wind power", "wind energy", "wind turbines"],
    "renewable energy": ["renewable energy", "renewables", "renewable power", "re100", "green power", "clean energy",
                         "open access", "power purchase agreement", "ppa", "hybrid renewable", "round the clock"],
    "green hydrogen": ["green hydrogen", "hydrogen"],
    "biomass": ["biomass", "bio fuel", "biofuel", "biofuels", "biogas", "compressed biogas", "cbg", "agro waste"],
    "electric vehicles": ["electric vehicles", "electric vehicle", "ev", "evs", "e mobility", "electric mobility",
                          "electric fleet", "electric buses", "ev100", "electric forklifts"],
    "waste heat recovery": ["waste heat recovery", "whr", "whrs", "heat recovery"],
    "carbon capture": ["carbon capture", "ccus", "ccs", "carbon sequestration", "carbon capture utilisation"],
    "sbti": ["sbti", "science based targets", "science based target", "science based", "sbt"],
    "net zero": ["netzero", "carbon neutral", "carbon neutrality"],
    "energy efficiency": ["energy efficiency", "energy efficient", "led lighting", "led", "vfd", "vfds",
                          "variable frequency drives", "energy audit", "energy audits", "bee star"],
    "alternative fuels": ["alternative fuels", "alternative fuel", "afr", "tsr", "thermal substitution", "rdf",
                          "refuse derived fuel", "fuel switch", "fuel switching", "cng", "lng", "png", "natural gas"],
    "afforestation": ["afforestation", "tree plantation", "plantation", "trees", "carbon sink", "miyawaki"],
    "internal carbon price": ["internal carbon price", "internal carbon pricing", "carbon price", "carbon pricing",
                              "shadow carbon price"],
    "green buildings": ["green building", "green buildings", "leed", "igbc", "griha"],
    "carbon credits": ["carbon credits", "carbon credit", "carbon offsets", "offsets", "recs", "i recs", "irecs",
                       "renewable energy certificates"],
    "heat pumps": ["heat pump", "heat pumps"],
}


@dataclass
class Entity:
    type: str
    value: object
    start: int
    end: int
    text: str
    method: str = "exact"
    score: float = 100.0


@dataclass
class LinkResult:
    tokens: list[str]            # prepped tokens
    masked: list[str]            # tokens with <co>/<sec> placeholders (numbers not yet masked)
    entities: list[Entity] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)

    def of(self, t: str) -> list[Entity]:
        return [e for e in self.entities if e.type == t]


class Linker:
    def __init__(self, kb, known_words: set[str] | None = None):
        self.kb = kb
        self.trie: dict = {}
        self.vocab: set[str] = set(STOP)
        for alias, ids in kb.aliases.items():
            self._add(alias.split(), "company", tuple(ids))
        for alias, name in KNOWN_ABSENT.items():
            self._add(norm_name(alias), "absent", name)
        sector_id = {s["name"]: s["id"] for s in kb.sectors}
        for sname, syns in SECTOR_SYNONYMS.items():
            for syn in [sname] + syns:
                self._add(norm_name(syn), "sector", sector_id[sname], vocab=True)
        for mid, m in METRICS.items():
            for ph in m["phrases"]:
                self._add(norm_name(ph), "metric", mid, vocab=True)
        for off in OFFTOPIC:
            for ph in off["phrases"]:
                self._add(norm_name(ph), "offtopic", off["key"], vocab=True)
        for term, phs in TECH_TERMS.items():
            for ph in phs:
                self._add(norm_name(ph), "tech", term, vocab=True)
        if known_words:
            self.vocab |= known_words
        self.alias_keys = sorted(kb.aliases)

    def _add(self, toks, typ, value, vocab=False):
        if not toks or any(t.startswith("<") for t in toks):
            return
        node = self.trie
        for t in toks:
            node = node.setdefault(t, {})
        cur = node.get("$")
        if cur is None or PRIORITY[typ] > PRIORITY[cur[0]]:
            node["$"] = (typ, value)
        if vocab:
            self.vocab.update(toks)

    def _fuzzy(self, s: str):
        """Best alias within a length-dependent edit tolerance; first letter must agree."""
        if len(s) < 5:
            return None
        cutoff = 84 if len(s) >= 7 else 83
        best = None
        for alias, _, _ in process.extract(s, self.alias_keys, scorer=fuzz.ratio, limit=8, score_cutoff=70):
            if alias[0] != s[0]:
                continue
            score = max(fuzz.ratio(s, alias), Levenshtein.normalized_similarity(s, alias) * 100)
            if score >= cutoff and (best is None or score > best[1]):
                best = (alias, score)
        return best

    def _longest(self, toks, i):
        node, best = self.trie, None
        j = i
        while j < len(toks) and toks[j] in node:
            node = node[toks[j]]
            j += 1
            if "$" in node:
                best = (j, node["$"])
        return best

    def link(self, text: str) -> LinkResult:
        raw = text
        toks = tokenize(prep(text))
        res = LinkResult(tokens=toks, masked=[])
        i = 0
        taken = [False] * len(toks)
        found: list[Entity] = []
        while i < len(toks):
            hit = self._longest(toks, i)
            if hit:
                j, (typ, val) = hit
                # "it" as a sector only when written as the acronym IT in the original text
                if typ == "sector" and toks[i] == "it" and j == i + 1 and not re.search(r"\bIT\b", raw):
                    i += 1
                    continue
                found.append(Entity(typ, val, i, j, " ".join(toks[i:j])))
                for k in range(i, j):
                    taken[k] = True
                i = j
            else:
                i += 1

        # fuzzy company matching on leftover spans (typos, missing letters)
        free_runs, run = [], []
        for k, t in enumerate(toks):
            if not taken[k] and t not in self.vocab and not t.startswith("<") and not NUMERIC.fullmatch(t):
                run.append(k)
            else:
                if run:
                    free_runs.append(run)
                run = []
        if run:
            free_runs.append(run)
        for run in free_runs:
            k = 0
            while k < len(run):
                matched = False
                for L in (3, 2, 1):
                    span = run[k:k + L]
                    if len(span) < L or span[-1] - span[0] != L - 1:
                        continue
                    s = " ".join(toks[span[0]:span[-1] + 1])
                    if len(s) < 4:
                        continue
                    m = self._fuzzy(s)
                    if m:
                        alias, score = m
                        found.append(Entity("company", tuple(self.kb.aliases[alias]), span[0], span[-1] + 1, s,
                                            method="fuzzy", score=round(score, 1)))
                        for q in span:
                            taken[q] = True
                        k += L
                        matched = True
                        break
                if not matched:
                    # a typo'd name followed by a word the gazetteers claimed ("ultratek cement")
                    pos = run[k]
                    nxt = next((e for e in found if e.start == pos + 1 and e.type in ("sector", "metric")
                                and e.end - e.start == 1), None)
                    m = self._fuzzy(f"{toks[pos]} {toks[pos + 1]}") if nxt else None
                    if m:
                        alias, score = m
                        found.remove(nxt)
                        found.append(Entity("company", tuple(self.kb.aliases[alias]), pos, pos + 2,
                                            f"{toks[pos]} {toks[pos + 1]}", method="fuzzy", score=round(score, 1)))
                    else:
                        res.unknown.append(toks[pos])
                    k += 1

        found.sort(key=lambda e: e.start)
        res.entities = found
        # masked token stream for the model
        out, k = [], 0
        spans = {e.start: e for e in found if e.type in ("company", "absent", "sector")}
        while k < len(toks):
            e = spans.get(k)
            if e:
                out.append(SEC if e.type == "sector" else CO)
                k = e.end
            else:
                out.append(toks[k])
                k += 1
        res.masked = out
        return res
