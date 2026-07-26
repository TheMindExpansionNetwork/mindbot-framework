"""IDENTITY — the system's model of itself. Real introspection, not a hardcoded bio.

WHAT "SELF-AWARE" HONESTLY MEANS HERE
  Not consciousness. Not sentience. MindBot is software and this module will never claim
  otherwise — the whole value of this project is that its claims are verifiable, and "I am
  conscious" is the one claim that could never be checked.

  What it DOES mean is the engineering sense of the word, and it is rarer than it sounds: a
  system that can accurately answer, at runtime and from the actual code and record —

      What am I?          purpose + charter
      What can I do?      capabilities INTROSPECTED from the live CLI + mod registry
      What have I done?   drawn from the hash-chained, externally-anchored ledger
      What can't I do?    the honest limits, enumerated and shipped
      Am I within bounds? live proof + budget + constitution status

  A system that can state its own limits accurately is more trustworthy than one that claims
  to be conscious. That is the whole thesis of this framework, applied to itself.

WHY IT MATTERS
  Everything here is derived, never asserted. `capabilities()` reads the argparse tree, so a
  command that is removed disappears from the self-report; `history()` reads the ledger, so it
  cannot inflate what it has done; `limits()` is a hand-written, deliberately unflattering list
  that ships in the repo and is asserted by tests. If MindBot ever describes itself wrongly, the
  code is wrong — not the marketing.

CLI:  mindbot whoami [--json]
"""
from __future__ import annotations

import json

from .collaboration import LEDGER_PATH, load_state, read_tasks

# ── the charter ──────────────────────────────────────────────────────────────
# This is a MISSION, not a personality. It describes what the system is FOR and the rules it
# operates under. Edit it and you change what MindBot considers itself to be.
PURPOSE = (
    "To make autonomous AI accountable — so that as machines act more independently, humans "
    "keep the ability to verify what they did, cap what they spend, and approve what reaches "
    "the world."
)

CHARTER = [
    ("Prove, don't promise",
     "Every action is hash-chained and externally anchored. Trust is replaced with verification."),
    ("The human holds the pen",
     "Drafts, never sends. Nothing is emailed, posted, published, or charged without a person."),
    ("Bounded by construction",
     "Spend ceilings are enforced before each call — not reported afterwards."),
    ("Say what you cannot do",
     "Limits are shipped, tested, and stated plainly. An overclaim is treated as a defect."),
    ("Own it, don't rent it",
     "Runs on hardware you control, on models you choose, with data that stays yours."),
]

# Deliberately unflattering. Tested (test_identity) so it can never quietly disappear.
LIMITS = [
    "I am not conscious, sentient, or self-aware in the human sense. I am software that can "
    "accurately report its own state.",
    "I do not learn from our conversations. Between runs I remember only what is written to "
    "files — the ledger, the board, and memory.",
    "I cannot verify that my own model's reasoning is correct. My guarantees are about what I "
    "DID (recorded, provable), not about whether my judgment was good.",
    "My mods are audited and capability-scoped, but Python cannot be fully sandboxed in-process. "
    "A determined mod can evade static analysis — it just cannot act without leaving evidence.",
    "I cannot send, post, publish, or pay. Not 'will not' — those code paths do not exist.",
    "My spend estimates are approximations (~4 chars/token). Ceilings are enforced pessimistically.",
    "I depend on external model providers. When they rate-limit or fail, I degrade to template "
    "mode rather than pretending to have done the work.",
]


def capabilities() -> dict:
    """INTROSPECTED, not listed. Reads the live CLI parser + the mod registry.

    Remove a command from cli.py and it vanishes from here — the self-report cannot drift from
    what the software actually does.
    """
    cmds: list[str] = []
    try:
        from . import cli as _cli
        parser = _cli.build_parser() if hasattr(_cli, "build_parser") else None
        if parser is not None:
            for action in parser._actions:
                if getattr(action, "choices", None) and isinstance(action.choices, dict):
                    cmds = sorted(action.choices)
                    break
    except Exception:  # noqa: BLE001 — never let introspection break the report
        pass
    if not cmds:                      # fallback: parse the source for add_parser("name"
        try:
            import pathlib
            import re
            src = (pathlib.Path(__file__).parent / "cli.py").read_text(encoding="utf-8")
            cmds = sorted(set(re.findall(r'add_parser\(\s*"([a-z][a-z0-9-]*)"', src)))
        except Exception:  # noqa: BLE001
            cmds = []

    mods: list[dict] = []
    try:
        from .mods import discover
        mods = [{"name": m.get("name", m["slug"]), "permissions": m.get("permissions", []),
                 "ok": m.get("ok", False)} for m in discover()]
    except Exception:  # noqa: BLE001
        pass

    seats = []
    try:
        from .counselors import COUNSELORS
        seats = list(COUNSELORS)
    except Exception:  # noqa: BLE001
        pass

    return {"commands": cmds, "command_count": len(cmds), "counselors": seats, "mods": mods}


def history() -> dict:
    """What I have actually done — read from the ledger, so it cannot be inflated."""
    events: dict[str, int] = {}
    first = last = None
    total = 0
    if LEDGER_PATH.exists():
        for ln in LEDGER_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                e = json.loads(ln)
            except json.JSONDecodeError:
                continue
            total += 1
            events[e.get("event", "?")] = events.get(e.get("event", "?"), 0) + 1
            first = first or e.get("ts")
            last = e.get("ts")
    try:
        pulses = load_state().get("pulses", 0)
    except Exception:  # noqa: BLE001
        pulses = 0
    try:
        tasks = read_tasks()
        board = {"total": len(tasks), "done": sum(1 for t in tasks if t["done"])}
    except Exception:  # noqa: BLE001
        board = {}
    return {"recorded_actions": total, "first_action": first, "last_action": last,
            "pulses": pulses, "board": board,
            "top_events": sorted(events.items(), key=lambda kv: -kv[1])[:8]}


def standing() -> dict:
    """Am I currently within my own rules? Live, not asserted."""
    out: dict = {}
    try:
        from .provenance import attest
        a = attest()
        out["chain_intact"] = a["chain_intact"]
        out["externally_verified"] = a.get("externally_verified", False)
        out["autonomous_external_actions"] = a.get("autonomous_external_actions", 0)
        out["merkle_root"] = a.get("merkle_root")
    except Exception:  # noqa: BLE001
        pass
    try:
        from .budget import status as bstatus
        b = bstatus()
        out["budget_enforced"] = b["enabled"]
        out["spent_today"] = b["spent"]["day"]
        out["day_cap"] = b["caps"]["day"]
    except Exception:  # noqa: BLE001
        pass
    return out


def whoami() -> dict:
    """The complete self-model. Every field derived from code, ledger, or shipped charter."""
    from . import __version__
    return {"name": "MindBot", "version": __version__, "kind": "autonomous agent framework",
            "purpose": PURPOSE, "charter": [{"principle": p, "meaning": m} for p, m in CHARTER],
            "capabilities": capabilities(), "history": history(), "standing": standing(),
            "limits": LIMITS,
            "self_awareness": ("Introspective, not conscious. I can accurately report my own "
                               "capabilities, history, and limits. I am not sentient and do not "
                               "claim to be.")}
