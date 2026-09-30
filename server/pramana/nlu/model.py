"""Pure-numpy inference for the Pramana query-understanding transformer.

Architecture (mirrors pipeline/slm/train.py exactly):
    token + position embeddings
    N x pre-LN encoder block: LN -> multi-head self-attention -> residual
                              LN -> GELU feed-forward -> residual
    final LN on the [CLS] position -> intent head, topic head

No sampling anywhere: the forward pass is a fixed function of the weights,
so the same query always yields the same distribution.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from .bpe import BPE


def _ln(x, g, b, eps=1e-5):
    mu = x.mean(-1, keepdims=True)
    var = ((x - mu) ** 2).mean(-1, keepdims=True)
    return (x - mu) / np.sqrt(var + eps) * g + b


def _gelu(x):
    return 0.5 * x * (1.0 + np.tanh(math.sqrt(2.0 / math.pi) * (x + 0.044715 * x ** 3)))


def _softmax(x, axis=-1):
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)


class IntentModel:
    def __init__(self, model_dir: Path):
        cfg = json.loads((model_dir / "config.json").read_text())
        self.cfg = cfg
        self.intents: list[str] = cfg["intents"]
        self.topics: list[str] = cfg["topics"]
        self.max_len: int = cfg["max_len"]
        self.heads: int = cfg["heads"]
        self.layers: int = cfg["layers"]
        self.bpe = BPE.from_json(json.loads((model_dir / "tokenizer.json").read_text()))
        w = np.load(model_dir / "weights.npz")
        self.w = {k: w[k].astype(np.float32) for k in w.files}
        self.known_words = set(cfg.get("known_words", []))
        self.n_params = int(sum(v.size for v in self.w.values()))

    def forward(self, text: str):
        cls = self._encode(text)
        W = self.w
        pi = _softmax(cls @ W["intent.w"].T + W["intent.b"])
        pt = _softmax(cls @ W["topic.w"].T + W["topic.b"])
        return pi, pt

    def embed(self, text: str) -> np.ndarray:
        """L2-normalised sentence embedding (the final [CLS] state), used for few-shot retrieval."""
        v = self._encode(text).astype(np.float64)
        return v / (np.linalg.norm(v) + 1e-12)

    def _encode(self, text: str) -> np.ndarray:
        """Pure function: text -> final [CLS] representation (no shared state, thread-safe)."""
        ids = np.array(self.bpe.encode(text, self.max_len), dtype=np.int64)
        mask = ids != 0
        W = self.w
        x = W["tok"][ids] + W["pos"][: len(ids)]
        d = x.shape[-1]
        hd = d // self.heads
        att_mask = np.where(mask[None, None, :], 0.0, -1e9).astype(np.float32)
        for l in range(self.layers):
            p = f"l{l}."
            h = _ln(x, W[p + "ln1.g"], W[p + "ln1.b"])
            qkv = h @ W[p + "qkv.w"].T + W[p + "qkv.b"]
            q, k, v = np.split(qkv, 3, axis=-1)
            T = q.shape[0]
            q = q.reshape(T, self.heads, hd).transpose(1, 0, 2)
            k = k.reshape(T, self.heads, hd).transpose(1, 0, 2)
            v = v.reshape(T, self.heads, hd).transpose(1, 0, 2)
            a = _softmax(q @ k.transpose(0, 2, 1) / math.sqrt(hd) + att_mask[0])
            o = (a @ v).transpose(1, 0, 2).reshape(T, d)
            x = x + o @ W[p + "proj.w"].T + W[p + "proj.b"]
            h = _ln(x, W[p + "ln2.g"], W[p + "ln2.b"])
            h = _gelu(h @ W[p + "ff1.w"].T + W[p + "ff1.b"]) @ W[p + "ff2.w"].T + W[p + "ff2.b"]
            x = x + h
        return _ln(x[0], W["lnf.g"], W["lnf.b"])

    def predict(self, text: str) -> dict:
        pi, pt = self.forward(text)
        order = np.argsort(-pi, kind="stable")
        torder = np.argsort(-pt, kind="stable")
        return {
            "intent": self.intents[int(order[0])],
            "intent_p": round(float(pi[order[0]]), 4),
            "intent_top3": [(self.intents[int(i)], round(float(pi[i]), 4)) for i in order[:3]],
            "topic": self.topics[int(torder[0])],
            "topic_p": round(float(pt[torder[0]]), 4),
            "pieces": self.bpe.pieces(text),
        }
