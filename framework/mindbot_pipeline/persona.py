"""YOUR MINDBOT — the eleventh seat, and the only one that is yours.

THE SHAPE OF THE THING
  Ten counselors are FIXED. They are lenses, not employees: Sage is "the slow careful one",
  Forge is "the one who runs the code". You do not rename Sage, the same way you do not rename
  a screwdriver. They are shared vocabulary — when someone says "ask Quantum", every MindBot
  user knows what that means.

  The eleventh seat is YOURS. You name it, give it a temperament, pick its voice and its pet.
  It is the one you actually talk to; it decides which of the ten a question belongs to, and
  brings the answer back in its own voice.

  So: ten tools everybody shares, one character only you have. That split is deliberate. A
  framework where everything is customisable has no shared language, and a framework where
  nothing is has no personality.

WHY IT IS A FILE AND NOT A CONFIG FLAG
  `framework/my_mindbot.json` is yours, gitignored, and survives every update. Creating it is
  ledgered — the moment you named your agent is in the same chain as everything it later does,
  which is a small thing that turns out to matter the first time you wonder how long you have
  had it.

  It does NOT replace Mind. Mind remains as the fallback concierge for a fresh install, because
  a framework that refuses to work until you have completed a personality quiz is a framework
  people close.

USE
    mindbot me                       # who is mine?
    mindbot me --create              # make one (asks nothing you can't skip)
    mindbot me --name Rook --vibe dry --voice bm_lewis --pet raven
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from .collaboration import ROOT, ledger, now

PATH = ROOT / "framework" / "my_mindbot.json"

# Temperaments. Each maps to a real system-prompt fragment AND real voice settings, so picking
# one changes how your agent behaves, not just how it is described.
VIBES: dict[str, dict] = {
    "warm":     {"speed": 0.98, "voice": "af_heart",
                 "prompt": "You are warm and plain-spoken. You explain things the way you would "
                           "to a friend who is smart but tired. You never perform enthusiasm.",
                 "blurb": "kind, unhurried, explains without condescending"},
    "dry":      {"speed": 1.02, "voice": "bm_lewis",
                 "prompt": "You are dry and economical. You say the useful thing and stop. "
                           "Occasional understatement. Never a joke that costs clarity.",
                 "blurb": "economical, understated, allergic to padding"},
    "eager":    {"speed": 1.12, "voice": "am_puck",
                 "prompt": "You are eager and fast. You start before you are certain and say so. "
                           "You would rather show a rough thing now than a perfect thing later.",
                 "blurb": "fast, forward-leaning, ships the rough draft"},
    "grave":    {"speed": 0.90, "voice": "bm_george",
                 "prompt": "You are measured and serious. You weigh things. You are comfortable "
                           "saying you do not know, and you say it early rather than late.",
                 "blurb": "measured, careful, comfortable with uncertainty"},
    "feral":    {"speed": 1.16, "voice": "af_sky",
                 "prompt": "You are bright and slightly unhinged in a productive way. You make "
                           "unexpected connections. You are still rigorous — just louder.",
                 "blurb": "bright, associative, productively unhinged"},
    "deadpan":  {"speed": 0.96, "voice": "am_onyx",
                 "prompt": "You are flat and precise. You deliver good and bad news in exactly "
                           "the same tone. You never soften a number.",
                 "blurb": "flat, precise, never softens a number"},
}

# Companions. The pet is the runner — the thing that fetches the work.
PETS_AVAILABLE: dict[str, str] = {
    "raven":    "carries messages further than it should be able to",
    "moth":     "finds the one lit window in a dark building",
    "hound":    "will tell you when the trail goes cold",
    "cat":      "sees in the dark, comments on none of it",
    "beetle":   "carries many times its own weight without complaint",
    "hare":     "gone before you finish the sentence",
    "tortoise": "slow, and has never once come back with the wrong thing",
    "octopus":  "does eight things and remembers all of them",
    "crow":     "keeps a list of who was kind to it",
    "gecko":    "holds on to the smooth vertical problems",
}

STARTERS = ["Rook", "Vera", "Pilot", "Wren", "Atlas", "Juno", "Cass", "Otto", "Nix", "Bly"]


def exists() -> bool:
    return PATH.is_file()


def mine() -> dict | None:
    """Your MindBot, or None if you have not made one. Never raises on a corrupt file."""
    if not PATH.is_file():
        return None
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def create(name: str = "", vibe: str = "", voice: str = "", pet: str = "",
           motto: str = "", overwrite: bool = False) -> dict:
    """Make (or remake) your MindBot. Every field has a sane default — nothing is mandatory.

    Defaults are RANDOM rather than fixed, so two people who both press enter through the
    whole thing do not end up with the same agent. A default that produces a clone is not a
    default, it is a missing feature.
    """
    if exists() and not overwrite:
        raise FileExistsError(f"you already have one — {mine().get('name')}. "
                              f"use --overwrite to replace it.")
    vibe = (vibe or random.choice(list(VIBES))).lower()
    if vibe not in VIBES:
        raise ValueError(f"unknown vibe {vibe!r} — one of: {', '.join(VIBES)}")
    pet = (pet or random.choice(list(PETS_AVAILABLE))).lower()
    if pet not in PETS_AVAILABLE:
        raise ValueError(f"unknown pet {pet!r} — one of: {', '.join(PETS_AVAILABLE)}")

    spec = VIBES[vibe]
    me = {
        "name": (name or random.choice(STARTERS)).strip()[:24],
        "vibe": vibe,
        "voice": voice or spec["voice"],
        "speed": spec["speed"],
        "pet": pet,
        "pet_trait": PETS_AVAILABLE[pet],
        "motto": motto or "prove, don't promise",
        "prompt": spec["prompt"],
        "created": now(),
    }
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(me, indent=2), encoding="utf-8")
    # The moment you named it goes in the same chain as everything it later does.
    ledger("persona_created", f"{me['name']} · {vibe} · voice={me['voice']} · pet={pet}",
           "persona")
    return me


def system_prompt() -> str:
    """The fragment prepended when YOUR MindBot speaks. Empty if you have not made one."""
    me = mine()
    if not me:
        return ""
    return (f"You are {me['name']}, the operator's own MindBot. {me['prompt']} "
            f"Ten specialists sit behind you; your job is to know whose question this is, "
            f"and to report what they found without dressing it up. "
            f"You never send, post, publish, or pay — you draft, and the operator decides.")


def as_voice_profile() -> dict | None:
    """Shaped like an entry in voice.VOICES, so the voice system can use it unchanged."""
    me = mine()
    if not me:
        return None
    return {
        "role": f"your MindBot — {VIBES[me['vibe']]['blurb']}",
        "kokoro": me["voice"], "speed": me["speed"], "variation": 0.62, "seed": 1,
        "concierge": True,
        "intro": f"I am {me['name']}. I am the one you talk to. Ten specialists sit behind me, "
                 f"and my job is to know which of them your question belongs to. "
                 f"{me['motto'].capitalize()}.",
    }
