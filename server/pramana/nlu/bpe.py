"""Byte-pair encoding tokenizer, implemented from scratch.

Words are split into characters plus an end-of-word marker, and the most
frequent adjacent pair is merged repeatedly (Sennrich et al., 2016).
Entity placeholders (<co>, <sec>, <num>, <pct>, <year>) are atomic tokens.
"""
from __future__ import annotations

import json
from collections import Counter

from .normalize import SPECIALS

PAD, UNK, CLS = "[PAD]", "[UNK]", "[CLS]"
EOW = "</w>"


def _word_symbols(word: str) -> tuple[str, ...]:
    if word in SPECIALS:
        return (word,)
    return tuple(word[:-1]) + (word[-1] + EOW,)


class BPE:
    def __init__(self, merges: list[tuple[str, str]], vocab: list[str]):
        self.merges = [tuple(m) for m in merges]
        self.rank = {m: i for i, m in enumerate(self.merges)}
        self.vocab = vocab
        self.index = {t: i for i, t in enumerate(vocab)}
        self.cache: dict[str, list[str]] = {}

    # ------------------------------------------------------------------ training
    @classmethod
    def train(cls, sentences: list[str], num_merges: int = 1500, min_freq: int = 2) -> "BPE":
        words = Counter(w for s in sentences for w in s.split())
        corpus = {_word_symbols(w): f for w, f in words.items()}
        merges: list[tuple[str, str]] = []
        for _ in range(num_merges):
            pairs: Counter = Counter()
            for sym, f in corpus.items():
                for a, b in zip(sym, sym[1:]):
                    pairs[(a, b)] += f
            if not pairs:
                break
            # deterministic: highest frequency, then lexicographic
            best, freq = min(pairs.items(), key=lambda kv: (-kv[1], kv[0]))
            if freq < min_freq:
                break
            merges.append(best)
            merged = best[0] + best[1]
            new = {}
            for sym, f in corpus.items():
                out, i = [], 0
                while i < len(sym):
                    if i < len(sym) - 1 and (sym[i], sym[i + 1]) == best:
                        out.append(merged)
                        i += 2
                    else:
                        out.append(sym[i])
                        i += 1
                new[tuple(out)] = new.get(tuple(out), 0) + f
            corpus = new
        symbols = sorted({s for sym in corpus for s in sym} | {a + b for a, b in merges}
                         | {c for w in words for c in w if w not in SPECIALS} | {c + EOW for w in words for c in w[-1:]})
        vocab = [PAD, UNK, CLS] + SPECIALS + [s for s in symbols if s not in SPECIALS]
        return cls(merges, vocab)

    # ------------------------------------------------------------------ encoding
    def word(self, w: str) -> list[str]:
        if w in self.cache:
            return self.cache[w]
        sym = list(_word_symbols(w))
        while len(sym) > 1:
            best, idx = None, -1
            for i in range(len(sym) - 1):
                r = self.rank.get((sym[i], sym[i + 1]))
                if r is not None and (best is None or r < best):
                    best, idx = r, i
            if best is None:
                break
            sym[idx:idx + 2] = [sym[idx] + sym[idx + 1]]
        self.cache[w] = sym
        return sym

    def encode(self, text: str, max_len: int) -> list[int]:
        ids = [self.index[CLS]]
        for w in text.split():
            for s in self.word(w):
                ids.append(self.index.get(s, self.index[UNK]))
        ids = ids[:max_len]
        return ids + [self.index[PAD]] * (max_len - len(ids))

    def pieces(self, text: str) -> list[str]:
        return [s for w in text.split() for s in self.word(w)]

    # ------------------------------------------------------------------ io
    def to_json(self) -> dict:
        return {"merges": [list(m) for m in self.merges], "vocab": self.vocab}

    @classmethod
    def from_json(cls, d: dict) -> "BPE":
        return cls([tuple(m) for m in d["merges"]], d["vocab"])

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self.to_json(), f)
