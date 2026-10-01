"""Company alias generation (run at build time, stored in kb.json).

For each company we derive the official name, the name without legal
suffixes, and a unique two-word prefix. Single-word aliases are only kept
when the word is not an ordinary English word, so "Page Industries" never
fires on "which page", and "Coal India" never fires on "coal".
"""
from __future__ import annotations

from collections import defaultdict

from .lexicon import CURATED_ALIASES, CURATED_GROUPS, STOP
from .normalize import norm_name

LEGAL = {"limited", "ltd", "the", "company", "corporation", "corp", "co", "of", "pvt", "private", "inc", "and"}


def strip_suffix(toks: list[str], drop_india: bool) -> list[str]:
    toks = list(toks)
    changed = True
    while toks and changed:
        changed = False
        if toks[-1] in LEGAL or (drop_india and toks[-1] == "india"):
            toks.pop()
            changed = True
    while toks and toks[0] == "the":
        toks.pop(0)
    return toks


def build_aliases(companies: list[dict], english_words: set[str]) -> dict[str, list[str]]:
    """Return alias string -> sorted list of company ids."""
    by_alias: dict[str, set[str]] = defaultdict(set)
    prefix_owner: dict[str, set[str]] = defaultdict(set)
    first_owner: dict[str, set[str]] = defaultdict(set)

    def ok(toks: list[str]) -> bool:
        if not toks:
            return False
        if all(t in STOP for t in toks):
            return False
        if len(toks) == 1:
            t = toks[0]
            return len(t) >= 3 and t not in STOP and t not in english_words and not t.isdigit()
        return True

    for c in companies:
        full = norm_name(c["name"])
        cands = [full, strip_suffix(full, False), strip_suffix(full, True)]
        for toks in cands:
            if ok(toks):
                by_alias[" ".join(toks)].add(c["id"])
        core = strip_suffix(full, True)
        if len(core) >= 3 and core[1] not in STOP and core[1] not in LEGAL:
            prefix_owner[" ".join(core[:2])].add(c["id"])
        if core:
            first_owner[core[0]].add(c["id"])

    for p, owners in prefix_owner.items():
        if len(owners) == 1 and ok(p.split()):
            by_alias[p] |= owners
    for w, owners in first_owner.items():
        if len(owners) == 1 and ok([w]):
            by_alias[w] |= owners

    name_to_id = {c["name"]: c["id"] for c in companies}
    for alias, name in CURATED_ALIASES.items():
        if name is None:
            continue
        if name not in name_to_id:
            raise ValueError(f"Curated alias target not in dataset: {name}")
        key = " ".join(norm_name(alias))
        by_alias[key] = {name_to_id[name]}  # curated wins over generated collisions

    for alias, group in CURATED_GROUPS.items():
        missing = [n for n in group if n not in name_to_id]
        if missing:
            raise ValueError(f"Curated group target not in dataset: {missing}")
        by_alias[" ".join(norm_name(alias))] = {name_to_id[n] for n in group}

    return {a: sorted(ids) for a, ids in sorted(by_alias.items())}
