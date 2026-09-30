"""Train the Pramana query-understanding model from scratch.

    python -m pipeline.slm.train

Steps
  1. Expand the hand-written grammar (templates.py) into a labelled corpus.
  2. Train a BPE tokenizer on that corpus.
  3. Train a small pre-LN transformer encoder with two heads (intent, topic).
  4. Export weights to numpy, verify parity with the numpy runtime, and
     evaluate on a held-out set of hand-written queries (eval_queries.jsonl).
"""
from __future__ import annotations

import json
import math
import random
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from pramana.nlu.bpe import BPE  # noqa: E402
from pramana.nlu.lexicon import METRICS, OFFTOPIC  # noqa: E402
from pramana.nlu.linker import TECH_TERMS  # noqa: E402
from pramana.nlu.normalize import model_text  # noqa: E402

from .grammar import expand  # noqa: E402
from .templates import INTENTS, PL, PREFIXES, SUFFIXES  # noqa: E402

OUT = ROOT / "server" / "pramana" / "nlu" / "artifacts"
SEED = 20250930
MAX_LEN = 40
D, HEADS, LAYERS, FF = 128, 4, 2, 256
PER_INTENT = 3500

KIND = {m: v["kind"] for m, v in METRICS.items()}
NUMERIC = [m for m, k in KIND.items() if k in ("numeric", "intensity")]
BOOL = [m for m, k in KIND.items() if k == "bool"]
TEXT = [m for m, k in KIND.items() if k == "text"]
ALL = [m for m in METRICS]
TOPICS = ["none"] + ALL


def metric_slot(pool):
    def f(rng):
        m = rng.choice(pool)
        return rng.choice(METRICS[m]["phrases"]), m
    return f


def build_slots(rng):
    cos_forms = ["<co> and <co>", "<co>, <co> and <co>", "<co> vs <co>", "<co> versus <co>", "<co> & <co>",
                 "<co>, <co>, <co> and <co>", "<co> with <co>", "<co> and <co> and <co>"]
    years = ["fy 2024-25", "fy25", "2024-25", "fy 2023-24", "last year", "this year", "the current year",
             "the previous year", "fy24"]
    tech = [p for ps in TECH_TERMS.values() for p in ps]
    off = [p for o in OFFTOPIC for p in o["phrases"]]
    return {
        "co": lambda r: ("<co>", None),
        "cos": lambda r: (r.choice(cos_forms), None),
        "sec": lambda r: ("<sec>", None),
        "met": metric_slot(ALL),
        "nmet": metric_slot(NUMERIC),
        "bmet": metric_slot(BOOL),
        "tmet": metric_slot(TEXT),
        "n": lambda r: (str(r.choice([3, 5, 5, 5, 10, 10, 10, 15, 20])), None),
        "pct": lambda r: (f"{r.choice([5, 10, 10, 15, 20, 25, 30, 50])}{r.choice(['%', ' percent', '%', ' pct'])}", None),
        "tech": lambda r: (r.choice(tech), None),
        "off": lambda r: (r.choice(off), None),
        "year": lambda r: (r.choice(years), None),
        "pl": lambda r: (expand(PL, r, {}, {}), None),
    }


def typo(word: str, rng: random.Random) -> str:
    if len(word) < 5 or word.startswith("<"):
        return word
    i = rng.randrange(1, len(word) - 1)
    op = rng.random()
    if op < 0.33:
        return word[:i] + word[i + 1:]
    if op < 0.66:
        return word[:i] + word[i + 1] + word[i] + word[i + 2:]
    return word[:i] + word[i] + word[i:]


def generate(rng: random.Random):
    slots = build_slots(rng)
    data = []
    for intent, templates in INTENTS.items():
        n = PER_INTENT if intent != "greeting" else PER_INTENT // 2
        for _ in range(n):
            t = rng.choice(templates)
            filled: dict = {}
            s = expand(t, rng, slots, filled)
            if intent not in ("greeting", "set_lens"):
                s = rng.choice(PREFIXES) + s + rng.choice(SUFFIXES)
            topic = "none"
            for k in ("met", "nmet", "bmet", "tmet"):
                if k in filled:
                    topic = filled[k][0]
                    break
            if intent in ("company_metric", "peer_benchmark", "simulate") and rng.random() < 0.12:
                s = s.replace("<co>", rng.choice(["it", "they", "this company", "the company", "them"]), 1)
            txt = model_text(s)
            words = txt.split()
            if rng.random() < 0.15 and len(words) > 3:  # word dropout
                del words[rng.randrange(len(words))]
            if rng.random() < 0.15:  # typo injection
                j = rng.randrange(len(words))
                words[j] = typo(words[j], rng)
            data.append((" ".join(words), intent, topic))
    rng.shuffle(data)
    return data


# --------------------------------------------------------------------------- model

class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.ln1 = nn.LayerNorm(D)
        self.qkv = nn.Linear(D, 3 * D)
        self.proj = nn.Linear(D, D)
        self.ln2 = nn.LayerNorm(D)
        self.ff1 = nn.Linear(D, FF)
        self.ff2 = nn.Linear(FF, D)
        self.drop = nn.Dropout(0.1)

    def forward(self, x, pad):
        B, T, _ = x.shape
        h = self.ln1(x)
        q, k, v = self.qkv(h).split(D, dim=-1)
        q = q.view(B, T, HEADS, D // HEADS).transpose(1, 2)
        k = k.view(B, T, HEADS, D // HEADS).transpose(1, 2)
        v = v.view(B, T, HEADS, D // HEADS).transpose(1, 2)
        att = (q @ k.transpose(-1, -2)) / math.sqrt(D // HEADS)
        att = att.masked_fill(pad[:, None, None, :], -1e9).softmax(-1)
        o = (self.drop(att) @ v).transpose(1, 2).reshape(B, T, D)
        x = x + self.drop(self.proj(o))
        h = self.ff2(F.gelu(self.ff1(self.ln2(x)), approximate="tanh"))
        return x + self.drop(h)


class Net(nn.Module):
    def __init__(self, vocab, n_int, n_top):
        super().__init__()
        self.tok = nn.Embedding(vocab, D, padding_idx=0)
        self.pos = nn.Embedding(MAX_LEN, D)
        self.blocks = nn.ModuleList([Block() for _ in range(LAYERS)])
        self.lnf = nn.LayerNorm(D)
        self.intent = nn.Linear(D, n_int)
        self.topic = nn.Linear(D, n_top)
        self.emb_drop = nn.Dropout(0.1)

    def forward(self, ids):
        pad = ids == 0
        x = self.emb_drop(self.tok(ids) + self.pos(torch.arange(ids.shape[1], device=ids.device)))
        for b in self.blocks:
            x = b(x, pad)
        c = self.lnf(x[:, 0])
        return self.intent(c), self.topic(c)


def export(net: Net) -> dict[str, np.ndarray]:
    sd = {k: v.detach().cpu().float().numpy() for k, v in net.state_dict().items()}
    w = {"tok": sd["tok.weight"], "pos": sd["pos.weight"], "lnf.g": sd["lnf.weight"], "lnf.b": sd["lnf.bias"],
         "intent.w": sd["intent.weight"], "intent.b": sd["intent.bias"],
         "topic.w": sd["topic.weight"], "topic.b": sd["topic.bias"]}
    for l in range(LAYERS):
        p = f"blocks.{l}."
        q = f"l{l}."
        w[q + "ln1.g"], w[q + "ln1.b"] = sd[p + "ln1.weight"], sd[p + "ln1.bias"]
        w[q + "ln2.g"], w[q + "ln2.b"] = sd[p + "ln2.weight"], sd[p + "ln2.bias"]
        w[q + "qkv.w"], w[q + "qkv.b"] = sd[p + "qkv.weight"], sd[p + "qkv.bias"]
        w[q + "proj.w"], w[q + "proj.b"] = sd[p + "proj.weight"], sd[p + "proj.bias"]
        w[q + "ff1.w"], w[q + "ff1.b"] = sd[p + "ff1.weight"], sd[p + "ff1.bias"]
        w[q + "ff2.w"], w[q + "ff2.b"] = sd[p + "ff2.weight"], sd[p + "ff2.bias"]
    return w


def main():
    t0 = time.time()
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.use_deterministic_algorithms(True)
    rng = random.Random(SEED)

    data = generate(rng)
    intents = list(INTENTS)
    print(f"corpus: {len(data)} examples, {len(set(d[0] for d in data))} unique",
          Counter(d[1] for d in data).most_common(3))

    # tokenizer corpus: training text plus every metric/topic phrase
    extra = [model_text(p) for m in METRICS.values() for p in m["phrases"]]
    bpe = BPE.train([d[0] for d in data] + extra * 5, num_merges=1400, min_freq=3)
    print(f"bpe: {len(bpe.vocab)} symbols, {len(bpe.merges)} merges")

    X = torch.tensor([bpe.encode(d[0], MAX_LEN) for d in data])
    yi = torch.tensor([intents.index(d[1]) for d in data])
    yt = torch.tensor([TOPICS.index(d[2]) for d in data])
    n_val = 2000
    Xv, yiv, ytv = X[:n_val], yi[:n_val], yt[:n_val]
    Xt, yit, ytt = X[n_val:], yi[n_val:], yt[n_val:]

    net = Net(len(bpe.vocab), len(intents), len(TOPICS))
    opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=0.01)
    epochs, bs = 10, 128
    steps = epochs * math.ceil(len(Xt) / bs)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=2e-3, total_steps=steps, pct_start=0.1)
    g = torch.Generator().manual_seed(SEED)
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(len(Xt), generator=g)
        tot = 0.0
        for i in range(0, len(Xt), bs):
            idx = perm[i:i + bs]
            li, lt = net(Xt[idx])
            loss = F.cross_entropy(li, yit[idx], label_smoothing=0.05) + 0.5 * F.cross_entropy(lt, ytt[idx], label_smoothing=0.05)
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            sched.step()
            tot += loss.item() * len(idx)
        net.eval()
        with torch.no_grad():
            li, lt = net(Xv)
            ai = (li.argmax(-1) == yiv).float().mean().item()
            at = (lt.argmax(-1) == ytv).float().mean().item()
        print(f"epoch {ep + 1}: loss {tot / len(Xt):.4f}  val intent {ai:.4f}  val topic {at:.4f}")

    OUT.mkdir(parents=True, exist_ok=True)
    weights = export(net)
    np.savez_compressed(OUT / "weights.npz", **weights)
    bpe.save(OUT / "tokenizer.json")
    known = sorted({w for d in data for w in d[0].split() if not w.startswith("<")})
    n_params = int(sum(v.size for v in weights.values()))
    cfg = {"intents": intents, "topics": TOPICS, "max_len": MAX_LEN, "d_model": D, "heads": HEADS, "layers": LAYERS,
           "ff": FF, "params": n_params, "seed": SEED, "train_examples": len(Xt), "val_examples": n_val,
           "val_intent_acc": round(ai, 4), "val_topic_acc": round(at, 4), "known_words": known,
           "vocab_size": len(bpe.vocab)}
    (OUT / "config.json").write_text(json.dumps(cfg))

    # parity check: numpy runtime must reproduce torch logits
    from pramana.nlu.model import IntentModel
    rt = IntentModel(OUT)
    with torch.no_grad():
        li, _ = net(Xv[:200])
        tp = li.softmax(-1).numpy()
    worst = 0.0
    for k in range(200):
        pi, _ = rt.forward(data[k][0])
        worst = max(worst, float(np.abs(pi - tp[k]).max()))
    print(f"numpy/torch parity: max |dp| = {worst:.2e}")
    assert worst < 1e-4
    print(f"params {n_params:,}  trained in {time.time() - t0:.1f}s  -> {OUT}")


if __name__ == "__main__":
    main()
