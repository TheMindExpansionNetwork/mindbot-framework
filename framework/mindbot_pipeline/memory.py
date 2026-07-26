"""MEMORY — local semantic recall, stdlib only, works everywhere (no pip, no server).

A tiny TF-IDF cosine index over an append-only JSONL store. Not a GPU vector DB —
on purpose: it runs on a Raspberry Pi, in WSL, offline, in 2045. When you outgrow
it, the store is plain JSONL — swap in Chroma/FAISS/sqlite-vec later without losing
a line. The framework's long-term memory the constitution can actually keep.

  store(text, tags)         -> append a memory
  search(query, k)          -> ranked [{score, text, tags, ts}]
CLI: cli remember "..."  ·  cli recall <query>  (recall falls back to this index)

Extend: the store is plain JSONL at COLLAB/memory.jsonl — to swap in a real vector DB, keep
store()/search() signatures and replace their bodies; nothing else in the framework needs to
change. To tune ranking, edit _tok (tokenizer) or vec/idf (the TF-IDF weighting).
"""

import json
import math
import re
from collections import Counter

from .collaboration import COLLAB, now

MEM = COLLAB / "memory.jsonl"
_TOKEN = re.compile(r"[a-z0-9]+")


def _tok(text):
    return [w for w in _TOKEN.findall(text.lower()) if len(w) > 2]


def store(text, tags=None, agent="operator"):
    """Append one memory. Returns the stored record."""
    rec = {"ts": now(), "agent": agent, "text": text.strip(), "tags": tags or []}
    MEM.parent.mkdir(parents=True, exist_ok=True)
    with MEM.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _load():
    if not MEM.exists():
        return []
    out = []
    for line in MEM.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def search(query, k=5):
    """TF-IDF cosine rank. Pure stdlib. Returns top-k records with scores."""
    docs = _load()
    if not docs:
        return []
    doc_toks = [_tok(d["text"] + " " + " ".join(d.get("tags", []))) for d in docs]
    N = len(docs)
    df = Counter()
    for toks in doc_toks:
        for w in set(toks):
            df[w] += 1
    idf = {w: math.log(1 + N / (1 + c)) for w, c in df.items()}

    def vec(toks):
        tf = Counter(toks)
        return {w: (tf[w] / len(toks)) * idf.get(w, math.log(1 + N)) for w in tf} if toks else {}

    qv = vec(_tok(query))
    if not qv:
        return []
    qn = math.sqrt(sum(v * v for v in qv.values())) or 1.0
    scored = []
    for d, toks in zip(docs, doc_toks):
        dv = vec(toks)
        if not dv:
            continue
        dot = sum(qv.get(w, 0) * dv.get(w, 0) for w in qv)
        dn = math.sqrt(sum(v * v for v in dv.values())) or 1.0
        score = dot / (qn * dn)
        if score > 0:
            scored.append({"score": round(score, 4), **d})
    scored.sort(key=lambda x: -x["score"])
    return scored[:k]
