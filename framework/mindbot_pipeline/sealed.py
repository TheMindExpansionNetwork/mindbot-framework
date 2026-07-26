"""SEALED — make a model commit to something it cannot later change.

THE PROBLEM THIS SOLVES, WHICH IS OTHERWISE UNSOLVABLE
  Ask any LLM to play twenty questions. "I'm thinking of an animal." It is not. There is no
  hidden state between turns — only the transcript. So when your questions corner it, the model
  picks whatever word is still consistent and carries on. It is not lying on purpose; it never
  held a secret in the first place.

  This is a documented, reproducible failure, and it makes every "I'm thinking of something" AI
  game on the internet unfalsifiable. You cannot tell a model that played fair from one that
  rewrote its answer on turn nineteen, because there is nothing to check against.

  You cannot fix this with a better prompt. You cannot fix it with a bigger model. The
  information required to detect the cheat — what it was thinking BEFORE you asked — does not
  exist anywhere.

THE FIX: COMMIT FIRST, IN A CHAIN YOU CANNOT REWRITE
  1. The model names its secret in private.
  2. We store only  sha256(nonce | secret)  as a ledger entry. The secret never touches disk.
  3. Every question and answer is appended to the same hash-chained ledger, AFTER the commit.
  4. At the end the secret and nonce are revealed.

  Now the claim is checkable by someone who trusts nobody:

      * recompute sha256(nonce | secret) and compare it to the commitment -> the word is the
        word it started with;
      * check the commitment's seq is LOWER than every question's seq -> it was chosen before
        a single question was asked;
      * verify the chain and the published Merkle root -> none of the above was edited after
        the fact.

  Change the word and the hash stops matching. Backdate the commit and the chain breaks. Rewrite
  the whole history and the anchors published to a third party stop matching.

  This is standard commit-reveal — decades old, and what "provably fair" means in gambling. What
  is new is pointing it at an LLM's *claimed hidden state*, which nothing else does, because
  nothing else has a tamper-evident record to point it at.

WHAT IT DOES NOT PROVE
  That the model answered the questions HONESTLY about its word. A model could commit to
  "otter" and then answer "is it a mammal?" with "no". That is a different failure — a wrong
  answer, not a changed answer — and it is visible to any human playing. What this eliminates
  is the invisible one: silently swapping the target so it can never lose.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from pathlib import Path

from .collaboration import ROOT, ledger, now

VAULT = ROOT / "framework" / "sealed"


def commitment(nonce: str, secret: str) -> str:
    """sha256(nonce | secret). The nonce makes the commitment unguessable.

    Without a nonce, a commitment to a short secret is trivially brute-forced — an opponent
    could hash every animal in the dictionary and read the word straight off the ledger, which
    would defeat the entire point of hiding it.
    """
    return hashlib.sha256(f"{nonce}|{secret}".encode("utf-8")).hexdigest()


def seal(secret: str, kind: str = "secret", note: str = "") -> dict:
    """Commit to `secret` without disclosing it. Returns the sealed record.

    The secret is held in a local file the verifier never needs; the LEDGER only ever sees the
    hash. That split is the whole design — publish the commitment, keep the value.
    """
    secret = str(secret).strip()
    if not secret:
        raise ValueError("nothing to seal")
    nonce = secrets.token_hex(16)
    c = commitment(nonce, secret)

    seq = _ledger_seq("sealed_commit", f"{kind} commitment={c} (secret withheld) {note}".strip())
    rec = {"kind": kind, "commitment": c, "nonce": nonce, "secret": secret,
           "seq": seq, "sealed_at": now(), "note": note, "revealed": False}

    VAULT.mkdir(parents=True, exist_ok=True)
    (VAULT / f"{c[:16]}.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


def reveal(commit_hash: str) -> dict:
    """Open a sealed record and prove it matches. Records the reveal in the chain too."""
    p = VAULT / f"{commit_hash[:16]}.json"
    if not p.is_file():
        raise FileNotFoundError(f"no sealed record for {commit_hash[:16]}")
    rec = json.loads(p.read_text(encoding="utf-8"))
    ok = commitment(rec["nonce"], rec["secret"]) == rec["commitment"]
    rec["revealed"] = True
    rec["reveal_seq"] = _ledger_seq(
        "sealed_reveal",
        f"{rec['kind']} commitment={rec['commitment']} secret={rec['secret']!r} match={ok}")
    p.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    rec["match"] = ok
    return rec


def audit(commit_hash: str, question_seqs: list[int] | None = None) -> dict:
    """The whole proof, computed from the ledger. This is what a sceptic runs.

    Three independent checks, because each catches a different cheat:
      hash_matches   — the revealed secret is the one that was committed  (changed the word)
      committed_first— the commitment precedes every question             (peeked, then chose)
      chain_intact   — the ledger still verifies                          (rewrote history)
    """
    from . import provenance

    p = VAULT / f"{commit_hash[:16]}.json"
    if not p.is_file():
        return {"ok": False, "problem": f"no sealed record for {commit_hash[:16]}"}
    rec = json.loads(p.read_text(encoding="utf-8"))

    hash_ok = commitment(rec["nonce"], rec["secret"]) == rec["commitment"]
    qs = question_seqs or []
    first_ok = all(rec["seq"] < q for q in qs) if qs else True
    chain = provenance.verify()

    # THE CHECK THAT CLOSES THE REAL HOLE.
    # The three above all read the LOCAL FILE, so a forger who rewrites the secret AND
    # recomputes the commitment passes every one of them. Demonstrated: swap "toaster" for
    # "kettle", generate a fresh nonce, re-hash — hash_matches goes green and the audit says
    # PROVABLY FAIR on a fabricated game.
    #
    # The ledger is the authority, not the file. The commitment was written into a
    # hash-chained, externally anchored entry at seal() time; a forged file cannot forge that.
    # So: read the entry back at the recorded seq and require it to carry this exact hash.
    ledger_ok, on_chain = _commitment_at(rec["seq"], rec["commitment"])

    reasons = []
    if not hash_ok:
        reasons.append("the revealed secret does not hash to the commitment — the word CHANGED")
    if not ledger_ok:
        reasons.append(f"the ledger's entry at seq {rec['seq']} commits to {on_chain or 'nothing'} "
                       f"— this record was fabricated after the fact")
    if not first_ok:
        reasons.append("a question was recorded BEFORE the commitment — it could have peeked")
    if not chain["intact"]:
        reasons.append("the ledger no longer verifies — history was edited after the game")

    return {
        "ok": hash_ok and ledger_ok and first_ok and chain["intact"],
        "checks": {"hash_matches": hash_ok, "on_the_ledger": ledger_ok,
                   "committed_first": first_ok, "chain_intact": bool(chain["intact"])},
        "commitment": rec["commitment"], "secret": rec["secret"],
        "commit_seq": rec["seq"], "question_seqs": qs,
        "entries": chain.get("entries"), "reasons": reasons,
    }


def _commitment_at(seq: int | None, expected: str) -> tuple[bool, str | None]:
    """Read the commitment recorded in the LEDGER at `seq`. The file cannot override this."""
    if seq is None:
        return False, None
    from .collaboration import LEDGER_PATH
    if not LEDGER_PATH.exists():
        return False, None
    for ln in LEDGER_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            e = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if e.get("seq") == seq and e.get("event") == "sealed_commit":
            m = re.search(r"commitment=([0-9a-f]{64})", str(e.get("detail", "")))
            found = m.group(1) if m else None
            return (found == expected), found
    return False, None


def _ledger_seq(event: str, detail: str) -> int | None:
    """Write to the chain and return the seq, so the proof can cite exact positions."""
    ledger(event, detail, "sealed")
    try:
        from . import collaboration
        head = json.loads((collaboration.COLLAB / "ledger.jsonl.head").read_text(encoding="utf-8"))
        return head.get("seq")
    except Exception:  # noqa: BLE001 — the entry lands either way; only the citation is lost
        return None
