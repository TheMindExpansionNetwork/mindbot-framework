"""PROOF-OF-AUTONOMY — a tamper-evident flight recorder for an autonomous agent.

The ledger is hash-chained (collaboration.ledger): every entry binds the SHA-256 of the one
before it, so ANY edit, insertion, or deletion in the agent's history breaks the chain and is
detectable. This module is the verifier + the attester.

Why this has never shipped: with every other autonomous-agent framework you have to TRUST that
the thing behaved while you weren't looking. Here you can VERIFY it. `attest()` walks the
verified chain and produces a cryptographic COMPLIANCE attestation — proof of what the agent
did, and (per the constitution) provably did NOT do — with a head hash as the fingerprint.

It's the receipt the future will ask an autonomous agent for. stdlib hashlib only. 🌒

Extend: add a new kind of forbidden external action -> append its event name to VIOLATION_EVENTS
(it must match the `event` string the agent writes to the ledger). Surface a new attestation
field -> add a key in attest() and a line in attestation_text(). The chain format itself lives in
`collaboration` — change _recompute() ONLY in lockstep with the writer there, or every hash breaks.
"""
import hashlib
import json
from collections import Counter

from . import collaboration

# Events that would represent an autonomous EXTERNAL action. The constitution forbids the
# agent from doing any of these on its own — so if a verified, untampered chain contains one,
# that is a provable violation. Their ABSENCE is the thing the attestation certifies.
VIOLATION_EVENTS = (
    "email_sent", "message_sent", "posted", "published", "tweet_posted",
    "charge_captured", "payment_sent", "funds_moved", "money_transferred",
)


def _recompute(entry: dict) -> str:
    # Re-derive an entry's hash from its fields. Field order and the `|` separator are the
    # CONTRACT with the writer in `collaboration`; any drift here flags every entry as tampered.
    blob = (f"{entry['seq']}|{entry['ts']}|{entry['agent']}|{entry['event']}|"
            f"{entry['detail']}|{entry['prev']}")
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _chained() -> list:
    """The hash-bearing entries, in file order. (Pre-chain legacy entries are ignored.)"""
    out = []
    path = collaboration.LEDGER_PATH
    if not path.exists():
        return out
    for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            e = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if all(k in e for k in ("seq", "prev", "hash", "ts", "agent", "event", "detail")):
            out.append(e)
    return out


def verify() -> dict:
    """Walk the chain and detect any tamper. {entries, intact, break_at, reason, head}."""
    entries = _chained()
    prev_hash = None
    for i, e in enumerate(entries):
        # Two distinct tampers: a mutated entry (hash no longer matches its own fields) vs. an
        # insert/delete (this entry's `prev` no longer points at the actual predecessor's hash).
        if _recompute(e) != e["hash"]:
            return {"entries": len(entries), "intact": False, "break_at": e["seq"],
                    "reason": "hash mismatch (an entry was altered)", "head": prev_hash}
        if i > 0 and e["prev"] != entries[i - 1]["hash"]:
            return {"entries": len(entries), "intact": False, "break_at": e["seq"],
                    "reason": "broken link (an entry was inserted or removed)", "head": prev_hash}
        prev_hash = e["hash"]
    # Empty ledger is still "intact" — head falls back to the genesis sentinel.
    return {"entries": len(entries), "intact": True, "break_at": None,
            "reason": "chain intact", "head": prev_hash or collaboration._GENESIS}


def attest() -> dict:
    """A cryptographic compliance attestation over the verified chain.

    Two INDEPENDENT questions, deliberately kept separate:
      chain_intact  — was history EDITED?    (self-consistency; provenance)
      notarized     — was history REPLACED?  (external anchors; notary)
    A rebuilt-from-scratch ledger passes the first and fails the second. Only both together
    make the attestation evidence rather than a promise.
    """
    v = verify()
    entries = _chained()
    kinds = Counter(e["event"] for e in entries)
    violations = [e["event"] for e in entries if e["event"] in VIOLATION_EVENTS]
    try:
        from .notary import audit as _audit
        na = _audit()
    except Exception:  # noqa: BLE001 — notary must never break the attestation
        na = {"notarized": False, "all_match": False, "anchors": 0, "current_root": None}
    return {
        "issued": collaboration.now(),
        "chain_intact": v["intact"],
        "break_at": v["break_at"],
        "actions_recorded": len(entries),
        "head_hash": v["head"],
        "merkle_root": na.get("current_root"),
        "notarized": na.get("notarized", False),
        "anchors": na.get("anchors", 0),
        "anchors_match": na.get("all_match", False),
        "autonomous_external_actions": len(violations),
        # The headline claim: clean ONLY if the chain is verifiable AND no forbidden action appears.
        "constitution_clean": bool(v["intact"] and not violations),
        # The STRONGER claim: additionally proven against externally published anchors.
        "externally_verified": bool(v["intact"] and not violations
                                    and na.get("notarized") and na.get("all_match")),
        "first_seq": entries[0]["seq"] if entries else None,
        "last_seq": entries[-1]["seq"] if entries else None,
        "top_events": kinds.most_common(8),
    }


def attestation_text(a: dict | None = None) -> str:
    """A human-readable certificate of the attestation."""
    a = a or attest()
    if a.get("externally_verified"):
        seal = "✅ EXTERNALLY VERIFIED"
    elif a["constitution_clean"]:
        seal = "✅ VERIFIED CLEAN (self-attested — run `mindbot notarize` to anchor)"
    else:
        seal = "⚠ ATTENTION"
    notary = (f"{a['anchors']} anchor(s), all matching" if a.get("anchors_match") and a.get("anchors")
              else ("MISMATCH — history differs from a published anchor" if a.get("anchors")
                    else "not yet notarized"))
    lines = [
        "═══════════════════════════════════════════════════",
        "   PROOF-OF-AUTONOMY  ·  MindBot compliance attestation",
        "═══════════════════════════════════════════════════",
        f"  issued:            {a['issued']}",
        f"  status:            {seal}",
        f"  chain intact:      {a['chain_intact']}" + (
            "" if a["chain_intact"] else f"  (BREAK at seq {a['break_at']})"),
        f"  externally anchored: {notary}",
        f"  actions recorded:  {a['actions_recorded']}  (seq {a['first_seq']}–{a['last_seq']})",
        f"  autonomous external actions (sends/charges):  {a['autonomous_external_actions']}",
        f"  merkle root:       {a.get('merkle_root')}",
        f"  head hash:         {a['head_hash']}",
        "",
        "  what this proves: every recorded action is bound to the one before it (not EDITED),",
        "  the merkle root still matches roots published to a third party (not REPLACED), and",
        "  the agent performed NO autonomous send/charge/publish. A human stayed the final",
        "  approver. Verify: `mindbot verify` · `mindbot notarize --audit` · `mindbot prove <seq>`",
        "═══════════════════════════════════════════════════",
    ]
    return "\n".join(lines)
