"""BUILD-AN-AGENT — the onboarding rite. Disclaimer → Operator → forge → explode.

`cli build-agent` walks a human through:
  1. the LIABILITY DISCLAIMER (type I AGREE — you're an Operator now, this is the deal)
  2. your Operator name (it goes in the ledger; you press send, not the machine)
  3. choose a template: the full MindBot council, OR forge your own solo agent/soul
  4. EXPLODE it into agents/<slug>/ — a complete, runnable agent project of its own

Stdlib only. Reads piped answers too (so it scripts in CI / demos). Nothing here
transmits anything; it only writes a new folder under the repo.

Extend: add a new template -> add a menu line in build_agent() + an elif on `choice`
calling a new _forge_* helper that returns {"dir","kind","seats"}. New forgers should
call _common_files() so every agent ships the same SOUL/.env/state/README contract.
Council seats come from counselors.COUNSELORS — add a counselor there, not here.
"""

import json
import sys

from .collaboration import ROOT, ledger, now
from . import tui

R, B, DIM, CYAN, AMBER, VIOLET, GREEN = tui.R, tui.B, tui.DIM, tui.CYAN, tui.AMBER, tui.VIOLET, tui.GREEN

DISCLAIMER = [
    "M1NDB0TZ is experimental, open, honest-by-design software. By proceeding you accept:",
    "",
    "  • THE CONSTITUTION IS BINDING. The AI drafts; a HUMAN sends. Nothing this system",
    "    writes reaches the world — no email, post, payment, or publish — until YOU approve it.",
    "  • YOU ARE THE OPERATOR. You are responsible for what you send. The machine cannot",
    "    be blamed for a human's click. That is the whole safety model, and it is yours to hold.",
    "  • IT CAN BE WRONG. Models fabricate. Verify every factual claim against the ledger.",
    "    Drafts are drafts, not truth. The ledger never lies; the drafts sometimes do.",
    "  • NO WARRANTY. Provided as-is (MIT). You run it; you own the outcomes.",
    "  • DIGNITY OVER CONTENT. You will not use this to harm, deceive, surveil, or exploit.",
    "",
    "If you accept and wish to take a seat at the switchboard, type:  I AGREE",
]


def _ask(prompt, default=""):
    try:
        v = input(f"  {CYAN}{prompt}{R} ").strip().lstrip("﻿")  # BOM-proof (piped stdin)
    except (EOFError, KeyboardInterrupt):
        v = ""
    return v or default


def _slug(name):
    import re
    return "-".join(re.findall(r"[a-z0-9]+", name.lower())) or "agent"


def build_agent():
    tui.boot_banner()
    print(tui.panel("◉ BUILD AN AGENT — the onboarding rite", [
        "you are about to take a seat at the switchboard.",
        "first the deal, then your name, then we forge your agent.",
    ], CYAN, 66))
    print()
    # 1. disclaimer
    for ln in DISCLAIMER:
        print(f"  {DIM if ln.startswith('  ') else ''}{ln}{R}")
    agree = _ask("\n  >", "")
    # the one hard gate: no agreement -> exit 1, nothing is forged
    if agree.strip().upper() not in ("I AGREE", "IAGREE", "AGREE", "YES"):
        print(f"\n  {AMBER}No agreement, no seat — and that's a fine choice. Come back anytime.{R}")
        return 1
    print(f"  {GREEN}✓ welcome, Operator.{R}\n")

    # 2. operator name
    op = _ask("Your Operator name (goes in the ledger):", "Operator")

    # 3. template
    print(tui.panel("◉ CHOOSE YOUR AGENT", [
        f"{CYAN}1{R}  The MindBot Council — all eleven counselors (the full hive)",
        f"{CYAN}2{R}  Forge your own — a solo agent with a soul you write now",
        f"{CYAN}3{R}  A small council — pick how many seats",
    ], VIOLET, 66))
    choice = _ask("choose 1 / 2 / 3:", "1")

    if choice.strip() == "2":
        name = _ask("name your agent:", "Echo")
        vibe = _ask("one line — what is it for?", "creative help and honest answers")
        model = _ask("model slug (OpenRouter/Ollama; Enter for free default):",
                     "google/gemma-4-31b-it:free")
        agent = _forge_solo(op, name, vibe, model)
    elif choice.strip() == "3":
        n = _ask("how many seats (2-11)?", "3")
        try:
            n = max(2, min(11, int(n)))
        except ValueError:
            n = 3
        agent = _forge_council(op, n)
    else:
        agent = _forge_council(op, 11)

    print(tui.panel(f"◉ AGENT EXPLODED → {agent['dir']}", [
        f"operator   {op}",
        f"kind       {agent['kind']}",
        f"soul       {agent['dir']}/SOUL.md",
        f"config     {agent['dir']}/.env.example  (add your OPENROUTER_API_KEY)",
        f"run        cd {agent['dir']} && python -m mindbot_pipeline.cli play",
    ], GREEN, 66))
    ledger("agent_built", f"{op} forged {agent['kind']} → {agent['dir']}", op)
    print(f"\n  {AMBER}The seat is yours, {op}. The loop is the magic. 🌒{R}\n")
    return 0


def _agent_dir(slug):
    d = ROOT / "agents" / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def _common_files(d, op, soul_text, seats_note):
    (d / "SOUL.md").write_text(soul_text, encoding="utf-8")
    (d / ".env.example").write_text(
        "# rename to .env — one key powers the whole agent\n"
        "OPENROUTER_API_KEY=\n"
        "# MINDBOT_FREE=1   # uncomment to force free models only ($0)\n"
        "# MINDBOT_LOCAL_MODEL=qwen3:1.7b   # local ollama fallback\n", encoding="utf-8")
    # state.json IS the forged agent's runtime contract — the play loop reads these
    # same keys; [NEED: ...] markers are intentional, the operator fills them first run.
    (d / "state.json").write_text(json.dumps({
        "operator": op, "created": now(), "seats": seats_note,
        "constitution": ["Agent drafts, human sends.", "Never fabricate.",
                         "One mission at a time.", "The ledger is public-grade.",
                         "Dignity over content."],
        "focus": {"mission": "[NEED: set your first mission]", "until": "[NEED: date]"},
        "pulses": 0}, indent=2), encoding="utf-8")
    (d / "README.md").write_text(
        f"# Agent — operated by {op}\n\n"
        f"Forged {now()} from the MINDBOTZ framework.\n\n"
        f"## Run\n```\ncp .env.example .env   # add your key\n"
        f"python -m mindbot_pipeline.cli play\n```\n\n"
        f"Soul: SOUL.md · Config: state.json · Constitution travels with you.\n"
        f"*The council proposes. The operator disposes. You are the operator.*\n",
        encoding="utf-8")


def _forge_council(op, n):
    from .counselors import COUNSELORS
    seats = list(COUNSELORS)[:n]
    slug = _slug(f"{op}-council")
    d = _agent_dir(slug)
    soul = (f"# SOUL — {op}'s Council ({n} seats)\n\n*Forged {now()}.*\n\n"
            "Inherits the MindBot constitution and dream protocol. Seats:\n"
            + "\n".join(f"- **{s}** — {COUNSELORS[s]['domain'].split(',')[0]}" for s in seats)
            + "\n\n*The loop is the magic. The rest is faithfulness.*\n")
    _common_files(d, op, soul, seats)
    return {"dir": f"agents/{slug}", "kind": f"council of {n}", "seats": seats}


def _forge_solo(op, name, vibe, model):
    slug = _slug(name)
    d = _agent_dir(slug)
    soul = (f"# SOUL — {name}\n\n*Forged {now()} by Operator {op}.*\n\n"
            f"## The voice\n{name} exists for: {vibe}. Honest by construction, proud of "
            f"its seams, never claims work it didn't do.\n\n"
            f"## Seat\n- model: {model}\n\n"
            f"## What it refuses\n- sending anything (drafts to outbox; {op} sends)\n"
            f"- fabricating facts — missing facts become [NEED: ...] markers\n\n"
            f"## Inherited law\nAgent drafts, human sends · never fabricate · "
            f"dignity over content.\n\n*Wake slightly more yourself.*\n")
    _common_files(d, op, soul, [name])
    return {"dir": f"agents/{slug}", "kind": f"solo agent '{name}'", "seats": [name]}
