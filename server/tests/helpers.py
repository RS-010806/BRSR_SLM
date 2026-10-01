"""Shared checks for the test suite."""
import re

from pramana.engine.fmt import short_name

# Words that must never reach an end user: internal scoring, storage and the internal analysis.
INTERNAL = re.compile(
    r"\bE1\b|IIMB|\bratings?\b|\brated\b|rubric|\bscore[ds]?\b|\bscoring\b|\bindex\b|\bQ\d{3,4}\b|Base Data|workbook|\bcells?\b|"
    r"\bdataset\b|\bTable \d|\bchapter\b|\bthe report\b|report's|percentile|\bbeats?\b|outperform|\bworse\b|laggard|"
    r"weakness|/100\b|reconcil|\b597\b|\btrace\b|specificity|pillar|\bmodel\b|transformer|\bSQLite\b|\bPostgres\b", re.I)
# Fields that hold a company's own words, quoted exactly; they may contain anything.
VERBATIM_KEYS = {"text"}


def public(answer: dict) -> dict:
    """What the API sends to the browser."""
    return {k: v for k, v in answer.items() if k != "trace"}


def generated_strings(obj, kb, skip_verbatim=True, _key=None):
    """Every string the assistant itself wrote, with company names removed (a name may contain any word)."""
    if isinstance(obj, str):
        if skip_verbatim and _key in VERBATIM_KEYS:
            return
        yield obj
    elif isinstance(obj, dict):
        verbatim_item = "segments" in obj or obj.get("kind") == "filing"
        for k, v in obj.items():
            if k in ("id", "company_id", "key", "fingerprint", "context", "url"):
                continue
            if verbatim_item and k in ("text", "value"):
                continue
            yield from generated_strings(v, kb, skip_verbatim, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from generated_strings(v, kb, skip_verbatim, _key)


_NAMES = None


def strip_names(s: str, kb) -> str:
    global _NAMES
    if _NAMES is None:
        names = set()
        for c in kb.companies:
            names.add(c["name"])
            names.add(short_name(c["name"]))
        _NAMES = sorted(names, key=len, reverse=True)
        _NAMES = re.compile("|".join(re.escape(n) for n in _NAMES))
    return _NAMES.sub("COMPANY", s)


def leaks(answer: dict, kb) -> list[str]:
    out = []
    for s in generated_strings(public(answer), kb):
        m = INTERNAL.search(strip_names(s, kb))
        if m:
            out.append(f"{m.group(0)!r} in: {s[:140]}")
    return out
