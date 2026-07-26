"""PETS — every counselor has a runner, and its stats are real.

THE IDEA
  A counselor thinks. Its PET fetches. The pet is the thing that actually goes and gets the
  work — the runner — so when Forge writes code, it is Forge's pet that carried the request out
  and dragged the result back.

WHY THIS IS NOT DECORATION
  Every stat below is DERIVED FROM THE HASH-CHAINED LEDGER. Nothing is stored, nothing is
  incremented by a game loop, nothing can be set by hand:

      level   from how many actions that counselor has actually recorded
      fed     from how recently it last worked
      bond    from how many distinct days it has shown up
      mood    from whether its recent work succeeded or degraded to template mode

  So a neglected pet is genuinely hungry — its counselor has not been used. A high-level pet
  genuinely did the work. You cannot cheat a pet's level without doing the work, because the
  work IS the ledger and the ledger is externally anchored.

  That makes the pets an honest, legible view of real activity, which is the only reason they
  belong in a project whose whole argument is "derived, not asserted". A fake XP bar here would
  be the same lie as a fake cost table.

  It also makes the CLI fun to open, which matters more than it sounds: a tool nobody enjoys
  running does not get run, and a framework nobody runs proves nothing.

USE
    mindbot pets                # the whole menagerie
    mindbot pets Forge          # one pet, in detail
    mindbot pets --feed Forge   # tells you how to feed it (do work with that counselor)
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime

# name · species · glyph · what it is FOR (the trait maps to how that counselor works)
PETS: dict[str, dict] = {
    "Mind":     {"name": "Echo",    "species": "owl",       "glyph": "🦉",
                 "trait": "remembers every errand it has ever run",
                 "runs": "your questions, to whichever counselor owns them"},
    "Sage":     {"name": "Tortoise", "species": "tortoise", "glyph": "🐢",
                 "trait": "slow, and has never once come back with the wrong thing",
                 "runs": "the hard problems, carefully"},
    "Forge":    {"name": "Rivet",   "species": "beetle",    "glyph": "🪲",
                 "trait": "carries eleven times its own weight in source code",
                 "runs": "builds, tests, and the stack traces nobody wants"},
    "Scribe":   {"name": "Quill",   "species": "magpie",    "glyph": "🐦",
                 "trait": "steals the good sentence and brings it home",
                 "runs": "drafts, docs, and anything a stranger has to read"},
    "Vanguard": {"name": "Bolt",    "species": "hare",      "glyph": "🐇",
                 "trait": "gone before you finish the sentence",
                 "runs": "first drafts, at speed, wrong in useful ways"},
    "Quantum":  {"name": "Abacus",  "species": "spider",    "glyph": "🕷️",
                 "trait": "counts every leg twice before moving",
                 "runs": "sums, proofs, and the arithmetic you skipped"},
    "Seeker":   {"name": "Compass", "species": "hound",     "glyph": "🐕",
                 "trait": "will tell you when the trail goes cold instead of inventing one",
                 "runs": "research, sources, and honest dead ends"},
    "Spark":    {"name": "Ember",   "species": "fox",       "glyph": "🦊",
                 "trait": "brings back nine strange things and one brilliant one",
                 "runs": "ideas nobody asked for"},
    "Oracle":   {"name": "Iris",    "species": "cat",       "glyph": "🐈",
                 "trait": "sees in the dark, describes only what is there",
                 "runs": "images, footage, and the long view"},
    "Titan":    {"name": "Anchor",  "species": "ox",        "glyph": "🐂",
                 "trait": "does not hurry and does not drop things",
                 "runs": "migrations, backups, ten thousand files"},
    "Tempest":  {"name": "Squall",  "species": "starling",  "glyph": "🐦‍⬛",
                 "trait": "arrives as a flock — twenty drafts at once",
                 "runs": "volume, when volume is the strategy"},
}

# Level thresholds. Deliberately shallow at the start so a fresh install shows progress on the
# first real run — an empty menagerie that stays empty teaches nobody anything.
TIERS = [(0, "egg"), (5, "hatchling"), (25, "pup"), (75, "companion"),
         (200, "veteran"), (500, "familiar"), (1200, "legend")]


def _tier(actions: int) -> tuple[int, str]:
    lvl, name = 0, "egg"
    for i, (need, label) in enumerate(TIERS):
        if actions >= need:
            lvl, name = i, label
    return lvl, name


def _entries():
    """Read the ledger. The single source of truth for every stat here."""
    import json
    from .collaboration import LEDGER_PATH
    out = []
    if not LEDGER_PATH.exists():
        return out
    for ln in LEDGER_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue                      # a torn line must not starve the whole menagerie
    return out


import re as _re

# The studio and the firm record `agent="studio"` / `"firm"` and put the counselor in the
# DETAIL as `seat=Titan` or `[kokoro:...] Sage`. Reading only the agent field therefore missed
# the framework's most-used command entirely — Titan could complete a whole studio run and its
# pet would not move. Caught by feeding a starving pet and watching the count stay at 2.
_SEAT = _re.compile(r"\bseat=([A-Z][a-z]+)")


def _agent_of(entry: dict) -> str:
    """Which counselor does this ledger line belong to?

    The `agent` field is inconsistent by design — "Forge", "critic:Mind", "mod:x", "studio",
    "framework". So we check the agent first, then the detail's `seat=` marker. A line that
    names no counselor stays unattributed rather than being guessed at: an errand credited to
    the wrong pet is worse than one credited to none, because the whole point is that the
    number is trustworthy.
    """
    a = str(entry.get("agent", ""))
    for name in PETS:
        if name.lower() in a.lower():
            return name
    m = _SEAT.search(str(entry.get("detail", "")))
    if m and m.group(1) in PETS:
        return m.group(1)
    return ""


def stats(name: str, rows=None) -> dict:
    """Everything about one pet, computed from the ledger. Never stored."""
    if name not in PETS:
        raise ValueError(f"no pet for {name!r} — one of: {', '.join(PETS)}")
    rows = rows if rows is not None else _entries()
    mine = [e for e in rows if _agent_of(e) == name]

    actions = len(mine)
    lvl, tier = _tier(actions)
    days = sorted({e["ts"][:10] for e in mine if len(e.get("ts", "")) >= 10})
    last = mine[-1]["ts"][:16] if mine else ""

    # FED: how recently did this counselor actually work? Days since, not a countdown timer.
    hunger = None
    if days:
        try:
            y, m, d = (int(x) for x in days[-1].split("-"))
            hunger = (date.today() - date(y, m, d)).days
        except ValueError:
            hunger = None
    fed = ("starving" if hunger is None or hunger > 14 else
           "hungry" if hunger > 3 else
           "peckish" if hunger > 1 else "well fed")

    # MOOD: did its recent errands actually work, or degrade to template mode?
    recent = mine[-25:]
    degraded = sum(1 for e in recent if "template" in str(e.get("detail", "")).lower())
    mood = ("content" if not recent else
            "restless" if degraded > len(recent) * 0.5 else
            "eager" if degraded == 0 else "steady")

    nxt = next((n for n, _ in TIERS if n > actions), None)
    return {
        "counselor": name, **PETS[name],
        "actions": actions, "level": lvl, "tier": tier,
        "to_next": (nxt - actions) if nxt else 0, "next_tier": nxt,
        "bond": len(days), "first_seen": days[0] if days else "", "last_seen": last,
        "days_since": hunger, "fed": fed, "mood": mood,
        "favourite": Counter(e.get("event", "?") for e in mine).most_common(1)[0][0] if mine else "",
    }


def menagerie() -> list[dict]:
    """All eleven, in one ledger pass. Reading the file once matters — it is large."""
    rows = _entries()
    return [stats(n, rows) for n in PETS]


def bar(s: dict, width: int = 18) -> str:
    """Progress toward the next tier. Full bar at max tier rather than a misleading empty one."""
    if not s["next_tier"]:
        return "█" * width
    prev = max((n for n, _ in TIERS if n <= s["actions"]), default=0)
    span = max(1, s["next_tier"] - prev)
    done = max(0, min(width, round((s["actions"] - prev) / span * width)))
    return "█" * done + "·" * (width - done)


def feed_advice(name: str) -> str:
    """How to level a pet: do real work with its counselor. There is no other way."""
    hints = {
        "Mind": 'mindbot say --as Mind "..."   ·  mindbot whoami',
        "Sage": 'mindbot studio "<a hard question>" --seat Sage',
        "Forge": 'mindbot studio "<a script you need>" --kind code',
        "Scribe": 'mindbot studio "<something to document>" --kind write --seat Scribe',
        "Vanguard": "mindbot pulse   ·   mindbot autopilot --rounds 2",
        "Quantum": 'mindbot studio "<check this arithmetic>" --seat Quantum',
        "Seeker": 'mindbot studio "<research this>" --kind research',
        "Spark": 'mindbot studio "<something creative>" --seat Spark',
        "Oracle": "mindbot observe ./photos   ·   mindbot watch clip.mp4",
        "Titan": 'mindbot studio "<the unglamorous job>" --seat Titan',
        "Tempest": 'mindbot studio "<twenty variations of this>" --seat Tempest',
    }
    return hints.get(name, "mindbot studio \"...\"")
