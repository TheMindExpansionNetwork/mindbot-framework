"""Generate prompts/COUNCIL_SYSTEM_PROMPTS.md from counselors.py (single source of truth)."""
from pathlib import Path

from mindbot_pipeline.counselors import COUNSELORS, persona_prompt

out = [
    "# COUNCIL SYSTEM PROMPTS — one per seat, fully organized",
    "*Generated from counselors.py. Use verbatim in any runtime: OpenRouter, Ollama,",
    "Hermes, Claude Code, LM Studio. The constitution preamble rides inside every prompt.*",
    "",
]
for name, c in COUNSELORS.items():
    out += [
        f"## {name} · {c['model']} ({c['provider']})", "",
        "```", persona_prompt(name), "```", "",
        f"**Domain:** {c['domain']}  ",
        f"**Crons:** {', '.join(c['crons'])}  ",
        "**Routing:** ROUTES table in counselors.py — first match wins, Sage catches the rest.",
        "",
    ]
out += [
    "---", "## Conversation mode (the switchboard / `play` CLI)", "",
    "Append to any seat prompt for live chat:", "", "```",
    "You are in LIVE CONVERSATION with your Operator at the switchboard — answer in "
    "2-5 sentences, in voice, no reasoning tags, no markdown headers. Never claim "
    "work happened unless asked to plan it.", "```", "",
    "## Free-model caution (MINDBOT_FREE=1)", "",
    "Small/free models fabricate completed work in confident prose. Every draft they",
    "produce carries the outbox warning banner; status claims without ledger lines are fiction.",
]
Path(__file__).parent.joinpath("prompts").mkdir(exist_ok=True)
Path(__file__).parent.joinpath("prompts/COUNCIL_SYSTEM_PROMPTS.md").write_text(
    "\n".join(out), encoding="utf-8")
print("prompts written:", len(COUNSELORS), "seats")
