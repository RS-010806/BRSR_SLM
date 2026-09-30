"""A tiny generative grammar for synthetic training queries.

Syntax inside a template:
    (a|b|c)   choose one alternative (nesting allowed)
    [x]       optional (50%)
    {slot}    filled by a slot sampler
"""
from __future__ import annotations

import random
import re


def _parse_alts(s: str, i: int, close: str):
    """Parse until `close`, splitting on top-level '|'. Returns (alternatives, next_index)."""
    alts, cur, depth = [], [], 0
    while i < len(s):
        ch = s[i]
        if ch in "([":
            depth += 1
        elif ch in ")]":
            if depth == 0 and ch == close:
                alts.append("".join(cur))
                return alts, i + 1
            depth -= 1
        elif ch == "|" and depth == 0:
            alts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    raise ValueError(f"unbalanced template: {s}")


def expand(template: str, rng: random.Random, slots: dict, filled: dict) -> str:
    out, i = [], 0
    while i < len(template):
        ch = template[i]
        if ch == "(":
            alts, i = _parse_alts(template, i + 1, ")")
            out.append(expand(rng.choice(alts), rng, slots, filled))
        elif ch == "[":
            alts, i = _parse_alts(template, i + 1, "]")
            if rng.random() < 0.5:
                out.append(expand(rng.choice(alts), rng, slots, filled))
        elif ch == "{":
            j = template.index("}", i)
            name = template[i + 1:j]
            val, meta = slots[name](rng)
            if meta is not None:
                filled.setdefault(name, []).append(meta)
            out.append(val)
            i = j + 1
        else:
            out.append(ch)
            i += 1
    return re.sub(r"\s+", " ", "".join(out)).strip()
