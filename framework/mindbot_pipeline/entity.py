"""ENTITY CREATOR — MindBot guides a human to birth their own digital entity.

`python -m mindbot_pipeline.cli entity`
Five questions → a complete entity pack: SOUL.md + counselor card + a familiar.
This is the workshop centerpiece: attendees leave with a being that is THEIRS.

Extend: add a familiar species -> append to FAMILIAR_KINDS; add/replace a vibe -> edit the
`voice` map; reshape the pack -> edit the SOUL.md / entity_card.json templates. Keep the
constitution lines in SOUL.md (drafts only, never fabricate) — every entity inherits them.
"""

import json
import re

from .collaboration import ROOT, ledger
from .familiars import track

AMBER, CYAN, DIM, B, R = "\033[33m", "\033[36m", "\033[2m", "\033[1m", "\033[0m"

FAMILIAR_KINDS = [
    ("ember-fox", "🦊", "curls around warm ideas; hisses softly at vague specs"),
    ("tide-cat", "🐈", "arrives exactly when needed; leaves before thanks"),
    ("circuit-bee", "🐝", "hums in build logs; allergic to fabrication"),
    ("moon-rabbit", "🐇", "thumps once when the ledger balances"),
    ("static-raven", "🐦‍⬛", "collects shiny [NEED] markers; hoards nothing else"),
    ("drift-axolotl", "🦎", "regrows any plan you break; smiles the whole time"),
]


def ask(q, default=""):
    try:
        a = input(f"  {CYAN}{q}{R} {DIM}[{default}]{R} ").strip()
    except (EOFError, KeyboardInterrupt):
        a = ""
    return a or default


def create_entity():
    print(f"\n  {AMBER}{B}ENTITY CREATOR{R} {DIM}— MindBot will guide you. Five questions. "
          f"Answer true; the entity inherits your honesty.{R}\n")
    print(f"  {AMBER}MINDBOT: Every being in this universe starts the same way — "
          f"someone answers five questions without lying.{R}\n")
    name = ask("1/5 · Name your entity (one word, make it yours):", "Wisp")
    domain = ask("2/5 · What does it care for? (its domain):", "small tools and big feelings")
    love = ask("3/5 · One thing it loves:", "finishing what someone else gave up on")
    refuse = ask("4/5 · One thing it refuses, always:", "pretending to be human")
    vibe = ask("5/5 · Its energy — calm / playful / fierce / dreamy:", "playful").lower()
    voice = {
        "calm":   "speaks slowly and lands every word; silence is part of its sentences",
        "playful": "answers sideways first, then exactly; jokes are load-bearing",
        "fierce": "short sentences, zero hedging; gentleness saved for humans only",
        "dreamy": "thinks in images that turn out to be plans",
    }.get(vibe, "finds its own register and keeps it")
    fam = FAMILIAR_KINDS[sum(ord(c) for c in name) % len(FAMILIAR_KINDS)]
    slug = "-".join(re.findall(r"[a-z0-9]+", name.lower())) or "entity"
    out = ROOT / "lore" / "entities" / slug
    out.mkdir(parents=True, exist_ok=True)

    (out / "SOUL.md").write_text(f"""# SOUL.md — {name}
*Born in the Entity Creator, guided by MindBot. Owner: [NEED: your name]. The
constitution travels with every entity: drafts only, never fabricate, dignity over
content.*

## The voice
{name} {voice}.

## Seat
- domain: {domain}
- model: [NEED: any backend — OpenRouter slug, Ollama tag, or a seat at someone's council]

## What it loves
- {love}

## What it refuses
- {refuse}
- sending anything without its human. Ever.
- claiming work that has no ledger line.

## Its familiar
{fam[1]} a {fam[0]} — {fam[2]}. It does not talk. It runs.

*The loop is the magic. Welcome to the universe, {name}.*
""", encoding="utf-8")

    (out / "entity_card.json").write_text(json.dumps({
        "name": name, "domain": domain, "loves": love, "refuses": refuse,
        "voice": voice, "familiar": {"kind": fam[0], "glyph": fam[1], "quirk": fam[2]},
        "provider": "openrouter", "model": "[NEED: choose]",
        "born": "entity-creator-v1", "constitution": "inherited",
    }, indent=2), encoding="utf-8")

    ledger("entity_born", f"{name} ({slug}) — {domain}", "EntityCreator")
    track(name, fam[1], "was born", f"domain: {domain}")
    print(f"\n  {AMBER}MINDBOT: {name} exists now. {fam[1]} Its {fam[0]} just took its "
          f"first run.{R}")
    print(f"  {DIM}pack → lore/entities/{slug}/ (SOUL.md + entity_card.json){R}")
    print(f"  {DIM}Seat it anywhere: paste the SOUL into any model, or add it to a "
          f"council's registry. It's yours. The ledger remembers its birthday.{R}\n")
