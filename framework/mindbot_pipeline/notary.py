"""THE NOTARY — makes the agent's history externally verifiable, not just self-consistent.

THE HOLE THIS CLOSES
  A hash chain proves nobody EDITED history. It does NOT prove nobody REPLACED it. Delete the
  ledger, start a fresh chain, and a chain-only verifier happily reports "INTACT" — because the
  new history is perfectly self-consistent. Self-attestation is not proof; it is a promise with
  extra steps.

THE FIX — three properties no agent framework ships together:

  1. MERKLE ROOT. Every entry hash is a leaf; pairs are hashed upward to a single 32-byte root
     that commits to the ENTIRE history at a point in time. One number fingerprints everything.

  2. EXTERNAL ANCHORING. That root is written to ANCHORS.jsonl, which is COMMITTED TO GIT AND
     PUSHED. GitHub becomes the notary: a third party holding a timestamped, immutable copy of
     what our history looked like at seq N. To forge the past you would now also have to rewrite
     a public repository's commit history. Wholesale replacement stops being invisible.

  3. INCLUSION PROOFS (selective disclosure). Prove a SINGLE action happened — with an audit
     path of ~log2(n) hashes — WITHOUT revealing the rest of the ledger. An auditor verifies one
     entry against a published root and learns nothing else. That is the privacy property real
     compliance work needs and that dumping a log file can never provide.

Stdlib hashlib only (the 2045 rule). No chain, no token, no third-party service.

Extend: anchor cadence lives in the caller (`mindbot notarize`, or a git pre-commit hook).
Change the leaf definition ONLY in lockstep with collaboration's writer — every root depends on
it. Verification is deliberately independent of provenance.verify() so the two can disagree,
which is what surfaces a replacement.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import collaboration

ANCHORS = collaboration.COLLAB / "ANCHORS.jsonl"


# ── Merkle machinery ─────────────────────────────────────────────────────────
def _h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _leaf(entry_hash: str) -> str:
    # Domain-separated leaf/node prefixes (0x00 / 0x01) prevent second-preimage attacks where a
    # node hash could be passed off as a leaf. Standard practice (RFC 6962).
    return _h(b"\x00" + bytes.fromhex(entry_hash))


def _node(left: str, right: str) -> str:
    return _h(b"\x01" + bytes.fromhex(left) + bytes.fromhex(right))


def _levels(leaves: list[str]) -> list[list[str]]:
    """Build every level of the tree, bottom-up. Odd nodes are promoted (duplicated-free)."""
    if not leaves:
        return [[]]
    levels = [leaves]
    cur = leaves
    while len(cur) > 1:
        nxt = []
        for i in range(0, len(cur), 2):
            if i + 1 < len(cur):
                nxt.append(_node(cur[i], cur[i + 1]))
            else:
                nxt.append(cur[i])          # lone node rides up unchanged
        levels.append(nxt)
        cur = nxt
    return levels


def _entry_hashes() -> list[str]:
    """The chain's entry hashes, in order — the leaves of our tree."""
    return [e["hash"] for e in _chained_entries()]


def _chained_entries() -> list[dict]:
    out = []
    p = collaboration.LEDGER_PATH
    if not p.exists():
        return out
    for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            e = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if all(k in e for k in ("seq", "prev", "hash")):
            out.append(e)
    return out


def merkle_root(upto_seq: int | None = None) -> str:
    """Root committing to every entry (optionally only through `upto_seq`)."""
    entries = _chained_entries()
    if upto_seq is not None:
        entries = [e for e in entries if e["seq"] <= upto_seq]
    leaves = [_leaf(e["hash"]) for e in entries]
    if not leaves:
        return collaboration._GENESIS
    return _levels(leaves)[-1][0]


# ── inclusion proof: prove ONE entry without revealing the others ────────────
def prove(seq: int) -> dict | None:
    """Audit path for entry `seq`: the sibling hashes needed to recompute the root."""
    entries = _chained_entries()
    idx = next((i for i, e in enumerate(entries) if e["seq"] == seq), None)
    if idx is None:
        return None
    leaves = [_leaf(e["hash"]) for e in entries]
    levels = _levels(leaves)
    path, i = [], idx
    for lvl in levels[:-1]:
        sib = i ^ 1                                   # sibling index
        if sib < len(lvl):
            path.append({"dir": "R" if sib > i else "L", "hash": lvl[sib]})
        i //= 2
    e = entries[idx]
    return {
        "seq": seq, "entry_hash": e["hash"], "leaf": leaves[idx], "path": path,
        "root": levels[-1][0], "total_entries": len(entries),
        # the human-readable claim this proof substantiates
        "claim": {"ts": e.get("ts"), "agent": e.get("agent"), "event": e.get("event"),
                  "detail": e.get("detail")},
    }


def check_proof(proof: dict) -> bool:
    """Verify an inclusion proof STANDALONE — no ledger access required.

    This is the whole point: hand an auditor this dict and they can confirm the entry belongs to
    the published root while learning nothing about any other entry.
    """
    try:
        cur = proof["leaf"]
        if cur != _leaf(proof["entry_hash"]):
            return False
        for step in proof["path"]:
            cur = _node(step["hash"], cur) if step["dir"] == "L" else _node(cur, step["hash"])
        return cur == proof["root"]
    except Exception:  # noqa: BLE001 — a malformed proof is simply not a valid proof
        return False


# ── anchoring: git/GitHub becomes the third-party notary ────────────────────
def anchor(note: str = "") -> dict:
    """Append the current (seq, root, head) to ANCHORS.jsonl — commit+push it to notarize."""
    entries = _chained_entries()
    seq = entries[-1]["seq"] if entries else 0
    rec = {
        "ts": collaboration.now(), "seq": seq, "entries": len(entries),
        "merkle_root": merkle_root(), "chain_head": entries[-1]["hash"] if entries else collaboration._GENESIS,
        "note": note,
    }
    ANCHORS.parent.mkdir(parents=True, exist_ok=True)
    with ANCHORS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    collaboration.ledger("notary_anchor", f"seq={seq} root={rec['merkle_root'][:16]}…", "notary")
    return rec


def anchors() -> list[dict]:
    if not ANCHORS.exists():
        return []
    out = []
    for ln in ANCHORS.read_text(encoding="utf-8", errors="ignore").splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                pass
    return out


def audit() -> dict:
    """THE REAL TEST: does today's history still agree with every anchor ever published?

    Recomputes the Merkle root at each anchored seq from the CURRENT ledger. A mismatch means
    history was rewritten or replaced since that anchor was published — the exact attack a
    chain-only verifier cannot see.
    """
    rows, ok = [], True
    entries = _chained_entries()
    have = len(entries)
    last_seq = entries[-1]["seq"] if entries else 0
    for a in anchors():
        # can't re-derive an anchor whose entries no longer exist -> that IS the failure signal
        if a["seq"] > last_seq:
            rows.append({"anchored_at": a["ts"], "seq": a["seq"], "match": False,
                         "reason": "ledger is SHORTER than this anchor — history truncated or replaced"})
            ok = False
            continue
        recomputed = merkle_root(upto_seq=a["seq"])
        match = recomputed == a["merkle_root"]
        rows.append({"anchored_at": a["ts"], "seq": a["seq"], "match": match,
                     "reason": "matches published root" if match
                               else "ROOT MISMATCH — history at this point differs from what was published"})
        ok = ok and match
    return {
        "anchors": len(rows), "all_match": ok, "checks": rows,
        "current_seq": last_seq, "current_entries": have, "current_root": merkle_root(),
        # no anchors = nothing has been notarized yet; that is "unproven", not "broken"
        "notarized": bool(rows),
    }
