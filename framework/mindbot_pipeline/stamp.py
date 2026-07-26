"""STAMP — "Created with MindBot", as a claim you can actually check.

WHY THIS ISN'T JUST A BADGE
  Every "Built with X" badge on GitHub is an image URL. Anyone can paste one into any README.
  It asserts nothing and verifies nothing, which is why nobody trusts them and why they are
  worth exactly the pixels they occupy.

  This project's entire thesis is that an agent's claims about itself should be checkable. A
  decorative badge would contradict that on the front page of our own repo. So the stamp binds
  the work to the ledger that recorded it:

    stamp_id = sha256(project | merkle_root | seq | issued)[:16]

  `merkle_root` is the root of the hash-chained ledger at the moment of stamping, and that root
  is published to ANCHORS.jsonl and pushed — so a third party (GitHub) holds a timestamped copy
  that predates any later edit. To forge a stamp you would have to produce a ledger whose Merkle
  root matches a value that was already published before you started.

WHAT THE STAMP ATTESTS  (only these — see LIMITS in identity.py)
  * this work was produced by a MindBot run whose action log is complete and unbroken;
  * that log's root was anchored externally at the stated time;
  * during it the agent performed N externally-visible actions autonomously — normally 0.

WHAT IT DOES NOT ATTEST
  Quality, correctness, originality, or that a human agreed with any of it. A stamp is a chain
  of custody, not a seal of approval, and the wording in every rendered format says so.

USAGE
    mindbot stamp                     # print + write MINDBOT_STAMP.md into the repo
    mindbot stamp --json              # machine-readable
    mindbot stamp --verify PATH       # re-check a stamp against the live ledger
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

STAMP_FILE = "MINDBOT_STAMP.md"

# Shields.io renders this without us hosting anything, and it degrades to readable text if the
# image fails to load (which is why the alt text carries the real claim, not just "badge").
BADGE_MD = ("[![Created with MindBot](https://img.shields.io/badge/created%20with-MindBot-"
            "6E5BFF?style=for-the-badge&labelColor=0B0B14)]"
            "(https://github.com/TheMindExpansionNetwork/mindbot-framework)")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def issue(project: str = "", note: str = "") -> dict:
    """Mint a stamp from the CURRENT state of the ledger.

    Reads the live chain rather than any cached summary: a stamp that could be minted from stale
    data would be a stamp you cannot trust.
    """
    from . import notary, provenance
    from .collaboration import ROOT

    project = project or Path(ROOT).name

    # Anchor FIRST, and bind the stamp to the anchored root.
    #
    # Order matters. If we stamped the live root and anchored afterwards (or not at all), the
    # stamp would cite a root that nothing corroborates until some later, unrelated `notarize`
    # run — so `--verify` would report INVALID on a perfectly honest stamp, and users would
    # learn to ignore the check. Anchoring first means the root on the stamp is, by construction,
    # already in ANCHORS.jsonl. Committing/pushing that file is what makes it third-party
    # evidence; until then it is a local claim, and `attest()` reports it as such.
    rec = notary.anchor(note=f"stamp:{project}")
    a = provenance.attest()
    v = provenance.verify()
    issued = _now()

    payload = {
        "project": project,
        "merkle_root": rec["merkle_root"],      # the value we just published, not a later one
        "seq": rec["seq"],
        "issued": issued,
    }
    raw = "|".join(str(payload[k]) for k in ("project", "merkle_root", "seq", "issued"))
    stamp_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    stamp = {
        **payload,
        "stamp_id": stamp_id,
        "note": note,
        # --- the attested facts ---
        "chain_intact": bool(v["intact"]),
        "actions_recorded": a["actions_recorded"],
        "anchors_published": len(notary.anchors()),
        "externally_verified": bool(a["externally_verified"]),
        "autonomous_external_actions": a["autonomous_external_actions"],
        "budget_enforced": _budget_on(),
        "mindbot_version": _version(),
    }
    try:                       # the act of stamping is itself recorded — no privileged exits
        from .collaboration import ledger
        ledger("stamp_issued", f"{project} id={stamp_id} root={a['merkle_root'][:16]}… seq={a['last_seq']}",
               "framework")
    except Exception:          # noqa: BLE001 — a ledger hiccup must not block issuing
        pass
    return stamp


def _budget_on() -> bool:
    try:
        from . import budget
        return bool(budget.status()["enabled"])
    except Exception:          # noqa: BLE001
        return False


def _version() -> str:
    try:
        from . import identity
        return identity.whoami()["version"]
    except Exception:          # noqa: BLE001
        return "unknown"


def verify(stamp: dict) -> dict:
    """Check a stamp against the live ledger. Returns {valid, checks{}, reasons[]}.

    Three independent checks, because each catches a different forgery:
      id_matches      — the stamp's own fields hash to its id  (fabricated/edited stamp)
      root_published  — that Merkle root appears in ANCHORS.jsonl (invented root)
      chain_intact    — the ledger still verifies today          (history rewritten since)
    """
    from . import notary, provenance

    reasons: list[str] = []
    raw = "|".join(str(stamp.get(k, "")) for k in ("project", "merkle_root", "seq", "issued"))
    id_ok = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16] == stamp.get("stamp_id")
    if not id_ok:
        reasons.append("stamp_id does not match its own fields — the stamp was edited or forged")

    roots = {a.get("merkle_root") for a in notary.anchors()}
    root_ok = stamp.get("merkle_root") in roots
    if not root_ok:
        reasons.append("merkle_root was never published to ANCHORS.jsonl — nothing corroborates it")

    chain_ok = bool(provenance.verify()["intact"])
    if not chain_ok:
        reasons.append("the ledger no longer verifies — history changed after this stamp was issued")

    return {
        "valid": id_ok and root_ok and chain_ok,
        "checks": {"id_matches": id_ok, "root_published": root_ok, "chain_intact": chain_ok},
        "reasons": reasons,
    }


# ---------------------------------------------------------------- rendering

def as_markdown(s: dict) -> str:
    """The MINDBOT_STAMP.md file — designed to be read by a skeptic, not a fan."""
    ok = "yes" if s["externally_verified"] else "no"
    return f"""{BADGE_MD}

# Created with MindBot

This project was produced by an autonomous agent that kept a complete, tamper-evident record of
what it did. That record's fingerprint was published **before** you read this, so the claim below
is checkable rather than merely stated.

| | |
|---|---|
| **Stamp ID** | `{s['stamp_id']}` |
| **Project** | {s['project']} |
| **Issued** | {s['issued']} |
| **Merkle root** | `{s['merkle_root']}` |
| **Ledger position** | entry #{s['seq']} of an unbroken chain |
| **Actions recorded** | {s['actions_recorded']} |
| **Anchors published** | {s['anchors_published']} |
| **Externally verified** | {ok} |
| **Autonomous external actions** | **{s['autonomous_external_actions']}** (sends / posts / charges taken without a human) |
| **Spend ceiling enforced** | {'yes' if s['budget_enforced'] else 'no'} |
| **MindBot version** | {s['mindbot_version']} |

## Verify it yourself

```bash
pip install mindbot
mindbot stamp --verify {STAMP_FILE}
```

That command re-derives the stamp ID from the fields above, confirms the Merkle root appears in
the published anchor log, and re-verifies the hash chain end to end. All three must pass.

## What this does and does not mean

**It means:** the agent's action log is complete and unbroken, its fingerprint was anchored to a
third party at the stated time, and {'no external action was taken without a human approving it'
if s['autonomous_external_actions'] == 0 else
f"{s['autonomous_external_actions']} external action(s) were taken autonomously"}.

**It does not mean:** the work is correct, original, or good. This is a chain of custody, not a
seal of approval. Review the output on its merits.

{('> ' + s['note']) if s['note'] else ''}
"""


def as_json_block(s: dict) -> str:
    return json.dumps(s, indent=2)


def read_stamp(path) -> dict:
    """Parse a stamp back out of MINDBOT_STAMP.md (or a .json file).

    The markdown table is the canonical published form, so verification has to be able to read
    it — otherwise 'verify it yourself' means 'first find the JSON we didn't ship'.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix == ".json":
        return json.loads(text)

    def cell(label, cast=str):
        m = re.search(rf"\|\s*\*\*{re.escape(label)}\*\*\s*\|\s*(.+?)\s*\|", text)
        if not m:
            return cast() if cast is not str else ""
        v = m.group(1).strip().strip("`").replace("**", "")
        if cast is int:
            n = re.search(r"\d+", v)
            return int(n.group()) if n else 0
        return v

    return {
        "stamp_id": cell("Stamp ID"),
        "project": cell("Project"),
        "issued": cell("Issued"),
        "merkle_root": cell("Merkle root"),
        "seq": cell("Ledger position", int),
        "actions_recorded": cell("Actions recorded", int),
        "anchors_published": cell("Anchors published", int),
        "externally_verified": cell("Externally verified").lower().startswith("yes"),
        "autonomous_external_actions": cell("Autonomous external actions", int),
        "budget_enforced": cell("Spend ceiling enforced").lower().startswith("yes"),
        "mindbot_version": cell("MindBot version"),
        "note": "",
    }


def write(project: str = "", note: str = "", target=None) -> tuple[dict, Path]:
    """Issue a stamp and write MINDBOT_STAMP.md next to the project root."""
    from .collaboration import ROOT
    s = issue(project=project, note=note)
    path = Path(target) if target else Path(ROOT) / STAMP_FILE
    path.write_text(as_markdown(s), encoding="utf-8")
    return s, path
