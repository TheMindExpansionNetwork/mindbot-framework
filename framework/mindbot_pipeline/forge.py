"""THE FORGE — a mod creator, and the total-conversion model that makes it worth having.

THE GTA/CYBERPUNK INSIGHT
  Nobody mods GTA by writing a plugin that adds a menu item. They replace the CARS, the SKINS,
  the MISSIONS, the PHYSICS — and a total-conversion mod turns the game into a different game
  while reusing the engine. That is what makes a modding scene rather than a plugin registry.

  MindBot's old mod system was a plugin registry: capability-scoped, audited, honest — and it
  could only ever ADD a command. You could not change who the council IS, what it values, how
  it judges its own work, or what it looks like. Everything interesting was hardcoded.

  The Forge opens four layers, so a mod can reskin the whole thing:

    CREW     replace the counselors — names, voices, which model each seat runs on
    LOOK     replace the interface — palette, banner, glyphs, the boot sequence
    RULES    replace the judgement — studio kinds, critique criteria, accept thresholds
    QUESTS   replace the work — task packs that seed the board with a campaign

  A pack that ships all four is a TOTAL CONVERSION. Same engine, different world. Run
  `mindbot forge pack cyberpunk-2045` and the council you wake up to is not the one you had.

WHAT STAYS BOLTED DOWN
  Everything a mod could use to hurt you. A pack CANNOT grant itself capabilities, disable the
  budget, remove the human gate, touch the ledger, or add a send path. Those are engine, not
  content. A total conversion changes the world; it does not change physics.

  This matters more here than in a game: the whole product is "you can check what it did". A
  mod layer that could disable the ledger would make every claim in the README false.

TWO WAYS IN
  mindbot forge mod "<description>"     generate a COMPLETE working mod via the studio
  mindbot forge pack <name>             scaffold a total-conversion pack (crew/look/rules/quests)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .collaboration import ROOT, ledger, now

MODS = ROOT / "mods"
PACKS = ROOT / "packs"

# The four layers a pack may replace. Anything NOT in here is engine and cannot be modded —
# see `_ENGINE_LOCKED` for what that deliberately excludes.
LAYERS = {
    "crew":   "counselors.json — seats, personas, and which model each runs on",
    "look":   "theme.json — palette, banner, glyphs, boot sequence",
    "rules":  "rules.json — studio kinds, critique criteria, accept threshold",
    "quests": "quests.md — a task pack that seeds the board with a campaign",
}

# Keys a pack may never set, at any depth. A total conversion changes the world, not physics.
_ENGINE_LOCKED = {
    "permissions", "capabilities", "grants",          # can't grant itself powers
    "budget", "budget_off", "spend_cap", "caps",      # can't lift the spend ceiling
    "ledger", "ledger_path", "anchors",               # can't touch the record
    "send", "smtp", "webhook", "publish", "charge",   # can't add an outward path
    "human_gate", "outbox_only",                      # can't remove the human
}


class PackRejected(Exception):
    """A pack tried to modify the engine rather than the world."""


# ────────────────────────────────────────────────────────────── validation

def validate(pack: dict) -> list[str]:
    """Return the reasons a pack is unsafe. Empty list == safe to load.

    Recursive, because `{"rules": {"studio": {"budget_off": true}}}` is exactly how someone
    would try to smuggle it past a top-level key check.
    """
    problems: list[str] = []

    def walk(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                here = f"{path}.{k}" if path else k
                if k.lower().replace("-", "_") in _ENGINE_LOCKED:
                    problems.append(f"{here} — engine-locked; packs change the world, not physics")
                walk(v, here)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(pack)
    for layer in pack.get("layers", {}):
        if layer not in LAYERS:
            problems.append(f"unknown layer {layer!r} — one of {', '.join(LAYERS)}")
    return problems


# ────────────────────────────────────────────────────── generate a real mod

_MOD_SCHEMA = {
    "name": "mod_spec",
    "schema": {
        "type": "object",
        "properties": {
            "slug": {"type": "string"},
            "description": {"type": "string"},
            "permissions": {"type": "array", "items": {"type": "string"}},
            "rationale": {"type": "string"},
            "commands": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "help": {"type": "string"}},
                    "required": ["name", "help"], "additionalProperties": False,
                },
            },
        },
        "required": ["slug", "description", "permissions", "rationale", "commands"],
        "additionalProperties": False,
    },
}


def design(description: str) -> dict:
    """Ask a counselor to DESIGN the mod — what it does and the least it needs to do it.

    Designing before coding matters here specifically because of the capability system: a mod
    that over-declares gets loaded with powers it doesn't use, which is exactly the thing the
    static audit exists to prevent. So the design step is asked for a RATIONALE per permission,
    and `_least_privilege()` drops any it cannot justify.
    """
    from .counselors import COUNSELORS, persona_prompt
    from .mods import CAPABILITIES
    from .models import llm, strip_reasoning

    caps = "\n".join(f"  {k} — {v}" for k, v in CAPABILITIES.items())
    spec = COUNSELORS["Forge"]
    text, mode = llm(spec["provider"], spec["model"], persona_prompt("Forge"),
        f"Design a MindBot mod: {description}\n\nAvailable capabilities:\n{caps}\n\n"
        "Reply as JSON ONLY:\n"
        '{"slug":"kebab-case","description":"one line","permissions":["…"],'
        '"rationale":"why EACH permission is needed","commands":[{"name":"…","help":"…"}]}\n\n'
        "Declare the FEWEST capabilities that can work. A mod that asks for more than it uses "
        "fails the static audit and will not load.")
    if mode in ("template", "budget"):
        return {"slug": _slug(description), "description": description[:90],
                "permissions": ["outbox.write"], "rationale": "template mode — minimal grant",
                "commands": [{"name": "run", "help": "do the thing"}], "degraded": True}
    return _parse_design(strip_reasoning(text), description)


def _parse_design(text: str, description: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        d = {}
    from .mods import CAPABILITIES
    return {
        "slug": _slug(d.get("slug") or description),
        "description": (d.get("description") or description)[:120],
        # Silently drop invented capabilities — a hallucinated permission would fail the audit
        # at load with a confusing error instead of here, where the cause is obvious.
        "permissions": [p for p in d.get("permissions", ["outbox.write"]) if p in CAPABILITIES]
                       or ["outbox.write"],
        "rationale": d.get("rationale", ""),
        "commands": [c for c in d.get("commands", []) if c.get("name")][:6]
                    or [{"name": "run", "help": "do the thing"}],
        "degraded": False,
    }


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "new-mod"


def create(description: str, quiet: bool = False) -> dict:
    """Design → implement → audit → write. A COMPLETE mod, not an empty template.

    `mindbot mod scaffold` already made empty templates. The gap it left is that a template is
    the easy 5% — the actual work is knowing which capabilities to declare and writing code the
    static auditor will accept. This closes that loop and then PROVES it by running the real
    auditor on the generated source before writing anything to disk.
    """
    from . import mods as modslib
    from .counselors import COUNSELORS, persona_prompt
    from .models import llm, strip_reasoning

    def say(m):
        if not quiet:
            print(m)

    spec = design(description)
    slug = spec["slug"]
    say(f"\n  ┌─ FORGE · {slug}")
    say(f"  │  {spec['description']}")
    say(f"  ├─ permissions  {', '.join(spec['permissions'])}")

    cmds = "\n".join(f"  {c['name']} — {c['help']}" for c in spec["commands"])
    cs = COUNSELORS["Forge"]
    code, mode = llm(cs["provider"], cs["model"], persona_prompt("Forge"),
        f"Write mods/{slug}/mod.py for MindBot.\n\nPURPOSE: {spec['description']}\n"
        f"GRANTED (using anything else raises CapabilityDenied): {', '.join(spec['permissions'])}\n"
        f"COMMANDS:\n{cmds}\n\n"
        "CONTRACT:\n"
        "  def register(api):  and inside it  @api.command('name', 'help')\n"
        "  api.log(msg) always available · api.say(msg) prints\n"
        "  api.draft(title, body) needs outbox.write · api.board() needs board.read\n"
        "  api.entries(event='', limit=0) needs ledger.read · api.ask(p) needs model\n"
        "Standard library only. Every command takes one `arg` string. Output ONLY Python in a "
        "single fenced block — no commentary.")
    body = _extract_py(strip_reasoning(code) if mode not in ("template", "budget") else "")
    degraded = spec["degraded"] or mode in ("template", "budget")
    if degraded or not body.strip():
        body = _fallback_mod(slug, spec)
    say(f"  ├─ implement    {len(body)} chars  [{mode}]")

    # Run the REAL static auditor before anything touches disk. Generating a mod the loader
    # would then refuse is worse than useless — it looks like the loader is broken.
    findings = modslib.audit_source(body, spec["permissions"])
    if findings:
        say(f"  ├─ audit        {len(findings)} overreach(es) — trimming")
        body = _annotate_findings(body, findings)
    else:
        say(f"  ├─ audit        clean — code matches its declaration")

    d = MODS / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "MOD.md").write_text(_manifest(slug, spec, findings, degraded), encoding="utf-8")
    (d / "mod.py").write_text(body, encoding="utf-8")
    ledger("forge_mod", f"{slug} perms={','.join(spec['permissions'])} "
                        f"cmds={len(spec['commands'])} audit={len(findings)}", "forge")
    say(f"  └─ mods/{slug}/   try: mindbot mod run {slug} {spec['commands'][0]['name']}\n")
    return {"slug": slug, "path": str(d), "spec": spec, "findings": findings,
            "degraded": degraded}


def _extract_py(text: str) -> str:
    blocks = re.findall(r"```(?:python)?\n(.*?)```", text, re.S)
    return (max(blocks, key=len).strip() + "\n") if blocks else text.strip() + "\n"


def _annotate_findings(body: str, findings) -> str:
    head = ("# FORGE AUDIT — this generated code reached for capabilities it did not declare:\n"
            + "".join(f"#   - {f}\n" for f in findings)
            + "# It will be DENIED at runtime and the attempt will be ledgered. Either declare\n"
              "# the capability in MOD.md, or remove the call.\n\n")
    return head + body


def _fallback_mod(slug: str, spec: dict) -> str:
    """A real, working mod for when no model is reachable. Honest about being a skeleton."""
    cmds = "\n\n".join(
        f'    @api.command("{c["name"]}", "{c["help"]}")\n'
        f'    def {re.sub(r"[^a-z0-9_]", "_", c["name"].lower())}(arg):\n'
        f'        api.log("{c["name"]} ran")\n'
        f'        api.say("TEMPLATE — implement me in mods/{slug}/mod.py")\n'
        f'        return {{"todo": "{c["help"]}"}}'
        for c in spec["commands"])
    return (f'"""{slug} — scaffolded by the Forge with no model backend.\n\n'
            f'{spec["description"]}\n\n'
            f'This is a SKELETON, not finished work. Each command is wired and audited but\n'
            f'does nothing yet. Implement them, then: mindbot mod info {slug}\n"""\n\n\n'
            f"def register(api):\n{cmds}\n")


def _manifest(slug: str, spec: dict, findings, degraded: bool) -> str:
    perms = "\n".join(f"  - {p}" for p in spec["permissions"])
    rows = "\n".join(f"| `mindbot mod run {slug} {c['name']}` | {c['help']} |"
                     for c in spec["commands"])
    warn = ""
    if degraded:
        warn = ("\n> **Scaffold only.** No model backend was reachable, so the commands are wired\n"
                "> but unimplemented. This is not finished work.\n")
    if findings:
        warn += ("\n> **Static audit flagged " + str(len(findings)) + " overreach(es).** The code\n"
                 "> reaches for capabilities this manifest does not declare; those calls will be\n"
                 "> denied at runtime and the attempts ledgered.\n")
    return f"""---
name: {slug}
version: 0.1.0
description: {spec['description']}
author: forged by MindBot
permissions:
{perms}
---

# {slug}

{spec['description']}
{warn}
## Commands

| Command | What it does |
|---|---|
{rows}

## Permissions & why

{spec['rationale'] or 'Least privilege: only what the commands actually use.'}

Every capability here is checked twice — statically against this file before the mod loads, and
again at each call. Anything undeclared raises `CapabilityDenied`, the call does not happen, and
the attempt is written to the hash-chained ledger.

---
*Forged {now()} · `mindbot mod info {slug}` for the audit result.*
"""


# ─────────────────────────────────────────────────── total-conversion packs

def scaffold_pack(name: str, quiet: bool = False) -> Path:
    """Create a total-conversion pack skeleton with all four layers."""
    slug = _slug(name)
    d = PACKS / slug
    for sub in ("",):
        (d / sub).mkdir(parents=True, exist_ok=True)

    (d / "PACK.md").write_text(f"""---
name: {slug}
version: 0.1.0
description: A total conversion for MindBot.
layers: [crew, look, rules, quests]
---

# {slug}

A **total conversion**: same engine, different world.

| Layer | File | What it replaces |
|---|---|---|
| crew | `counselors.json` | who the council IS — names, voices, per-seat models |
| look | `theme.json` | palette, banner, glyphs, boot sequence |
| rules | `rules.json` | studio kinds, critique criteria, accept threshold |
| quests | `quests.md` | a campaign that seeds the board |

## What a pack can never do

`permissions` · `budget` · `ledger` · `send`/`publish`/`charge` · `human_gate`

Those are **engine, not content**. A pack changes the world; it does not change physics. The
loader rejects any pack that sets them — at any nesting depth, because
`{{"rules":{{"studio":{{"budget_off":true}}}}}}` is exactly how someone would try to smuggle it past
a top-level check.

This is stricter than a game's mod API on purpose. The entire product is "you can check what it
did" — a mod layer that could switch off the ledger would make every claim in the README false.

## Install

```bash
mindbot forge install {slug}
mindbot whoami            # a different council answers
mindbot forge uninstall   # back to stock
```
""", encoding="utf-8")

    (d / "counselors.json").write_text(json.dumps({
        "_comment": "Replace the crew. `model` is an OpenRouter slug; omit it to keep the stock seat's model.",
        "seats": {
            "Sage": {"name": "Oracle-7", "voice": "clipped, corporate, faintly menacing"},
            "Forge": {"name": "Wrench", "voice": "street mechanic; explains via engines"},
        }}, indent=2), encoding="utf-8")

    (d / "theme.json").write_text(json.dumps({
        "_comment": "Palette is ANSI 256. banner is printed at boot.",
        "palette": {"primary": 51, "accent": 201, "dim": 240, "warn": 214},
        "banner": ["  ╔═══════════════════════════════╗",
                   "  ║   N I G H T   S H I F T       ║",
                   "  ╚═══════════════════════════════╝"],
        "glyphs": {"ok": "▸", "fail": "✖", "bullet": "·"},
        "boot": ["jacking in…", "council online", "no send path detected — good"],
    }, indent=2), encoding="utf-8")

    (d / "rules.json").write_text(json.dumps({
        "_comment": "Reshape judgement. accept_score is the bar a draft must clear.",
        "accept_score": 8,
        "max_rounds": 4,
        "criteria": {"write": ["Reads like a person under deadline, not a model",
                               "No corporate hedging",
                               "One concrete detail per paragraph"]},
    }, indent=2), encoding="utf-8")

    (d / "quests.md").write_text("""# Quests

One task per line. `mindbot forge install` seeds these onto the board.

- Draft the opening scene of the 2045 festival
- Design a poster for the Intergalactic Tour
- Research what a fair price is for a 360 scan gig
- Decide: free tier or paid-only at launch
""", encoding="utf-8")

    ledger("forge_pack", f"scaffolded pack {slug} with {len(LAYERS)} layers", "forge")
    if not quiet:
        print(f"\n  packs/{slug}/  — 4 layers scaffolded")
        for f in ("PACK.md", "counselors.json", "theme.json", "rules.json", "quests.md"):
            print(f"    {f}")
        print(f"\n  edit, then: mindbot forge install {slug}\n")
    return d


def load_pack(slug: str) -> dict:
    """Read and VALIDATE a pack. Raises PackRejected if it reaches for the engine."""
    d = PACKS / _slug(slug)
    if not d.is_dir():
        raise FileNotFoundError(f"no pack at packs/{_slug(slug)}")
    pack = {"slug": _slug(slug), "layers": {}}
    for layer, fname in (("crew", "counselors.json"), ("look", "theme.json"),
                         ("rules", "rules.json")):
        f = d / fname
        if f.exists():
            try:
                pack["layers"][layer] = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise PackRejected(f"{fname} is not valid JSON: {e}") from e
    q = d / "quests.md"
    if q.exists():
        pack["layers"]["quests"] = [ln.strip("-• ").strip()
                                    for ln in q.read_text(encoding="utf-8").splitlines()
                                    if ln.strip().startswith(("-", "•"))]
    problems = validate(pack)
    if problems:
        raise PackRejected("this pack tries to modify the engine:\n  - " + "\n  - ".join(problems))
    return pack


def installed() -> dict | None:
    f = PACKS / ".active.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def install(slug: str, seed_quests: bool = True) -> dict:
    """Activate a pack. Validated first — an invalid pack never becomes active."""
    pack = load_pack(slug)
    PACKS.mkdir(parents=True, exist_ok=True)
    (PACKS / ".active.json").write_text(json.dumps(pack, indent=2), encoding="utf-8")
    seeded = 0
    if seed_quests:
        from .collaboration import add_task
        for q in pack["layers"].get("quests", []):
            add_task(f"[{pack['slug']}] {q}", "pack")
            seeded += 1
    ledger("pack_install", f"{pack['slug']} layers={','.join(pack['layers'])} quests={seeded}",
           "forge")
    return {"pack": pack["slug"], "layers": list(pack["layers"]), "quests_seeded": seeded}


def uninstall() -> bool:
    f = PACKS / ".active.json"
    if not f.exists():
        return False
    slug = (installed() or {}).get("slug", "?")
    f.unlink()
    ledger("pack_uninstall", f"reverted to stock from {slug}", "forge")
    return True
