"""THE STUDIO — the answer to "it just does the same thing."

WHAT WAS WRONG WITH THE OLD LOOP
  `nucleus.pulse()` treats every task identically: claim it, pick a persona, make ONE model
  call, write a .md file, done. A sonnet, a market analysis and a Python script all take the
  exact same path. There is no revision, no artifact that isn't markdown, and nothing carries
  from one pulse to the next.

  That is a persona-rotating text generator. It produces samey output because the STRUCTURE is
  samey — and no amount of better prompts or bigger models fixes a missing loop.

WHAT THE STUDIO ADDS  (three things, in order of how much they matter)

  1. TASKS HAVE KINDS. A `code` task plans, writes, and then actually RUNS its own tests in a
     subprocess. A `build` task emits HTML and parses it. A `research` task poses its own
     questions before answering them. Different work takes different shapes.

  2. A CRITIQUE LOOP. A DIFFERENT counselor reviews the draft against explicit, per-kind
     criteria, scores it 0-10, and lists concrete fixes. Below threshold, it goes back for a
     revision round carrying those notes. This is the single biggest quality lever here: one
     shot at a blank page is the worst way to get good work out of a model, and it is exactly
     what the old loop did.

  3. EVERY ROUND IS LEDGERED. This is the part no other framework can copy. The critique loop
     is hash-chained like everything else, so you can PROVE a piece of work was reviewed three
     times and show what changed at each round. Provenance of *revision*, not just of output.

DESIGN NOTE — WHY THE CRITIC IS A DIFFERENT SEAT
  Asking the same model instance to critique its own fresh output reliably produces "looks
  great!". A separate seat with a separate persona and explicit scoring criteria disagrees far
  more usefully. It is not true independence — same provider, often the same weights — and the
  docstring says so rather than overselling it.

DEGRADED MODE
  With no model reachable, every stage returns a template. The loop still runs, still critiques,
  still ledgers, and the artifact says plainly that it is scaffolding. A $0 demo that pretends
  to be real work would poison the one thing this project sells.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .collaboration import ROOT, ledger, now
from .counselors import COUNSELORS, persona_prompt
from .models import llm, strip_reasoning

# How good is good enough, and how many times will we go around. Both deliberately modest:
# each revision round is another model call, and the returns fall off a cliff after ~2.
ACCEPT_SCORE = 7
MAX_ROUNDS = 3

OUT = ROOT / "framework" / "studio"


# ─────────────────────────────────────────────────────────────────── kinds

# Each kind declares: which seats suit it, what it produces, how it is judged, and what its
# stages are. Adding a kind is a dict entry — no changes to the engine below.
# SEATS ARE THE REAL ROSTER. Checked against counselors.COUNSELORS, not invented:
#   Sage (lead reasoning) · Forge (coder) · Scribe (docs/code writing) · Vanguard (momentum)
#   Quantum (math/logic) · Seeker (research) · Spark (creative) · Oracle (multimodal/vision)
#   Titan (heavy lifting) · Tempest (fast creative) · Mind (curator, closes loops)
# `_validate_seats()` at import time fails loudly if any of these drift — a KeyError deep in a
# batch run is a miserable way to discover a typo.
KINDS: dict[str, dict] = {
    "write": {
        "ext": "md",
        "seats": ["Tempest", "Scribe", "Spark"],
        "critic": "Mind",
        "criteria": [
            "Says something specific — no filler, no throat-clearing preamble",
            "Every claim is either supported or explicitly marked as opinion",
            "Reads like a person wrote it, not a model completing a form",
            "Ends where it should, rather than summarizing itself",
        ],
        "stages": ["draft"],
    },
    "research": {
        "ext": "md",
        "seats": ["Seeker", "Quantum", "Sage"],
        "critic": "Mind",
        "criteria": [
            "Answers the question that was actually asked",
            "Separates what is known from what is inferred from what is unknown",
            "Names the strongest counter-argument to its own conclusion",
            "States what would change the conclusion",
        ],
        # Posing the questions FIRST measurably beats answering cold — it forces the model to
        # decompose before it commits to a position.
        "stages": ["questions", "answer"],
    },
    "code": {
        "ext": "py",
        "seats": ["Forge", "Titan"],
        "critic": "Quantum",
        "criteria": [
            "Actually runs — no undefined names, no unimported modules",
            "Handles the obvious failure case rather than assuming happy path",
            "No dependency that isn't stdlib",
            "A reader can tell WHY, not just what",
        ],
        "stages": ["plan", "implement"],
        "executes": True,          # this kind gets a real subprocess test — see _run_python
    },
    "build": {
        "ext": "html",
        "seats": ["Oracle", "Forge"],
        "critic": "Spark",
        "criteria": [
            "Self-contained — no external CDN, font, or script",
            "Legible on both a light and a dark background",
            "Works at phone width without horizontal scrolling",
            "Looks deliberate rather than defaulted",
        ],
        "stages": ["design", "implement"],
        "validates": True,
    },
    "decide": {
        "ext": "md",
        "seats": ["Sage", "Quantum", "Titan"],
        "critic": "Vanguard",
        "criteria": [
            "Gives a RECOMMENDATION, not a balanced survey",
            "States the cost of being wrong",
            "Names what it would take to change the recommendation",
            "Honest about which option the author is biased toward",
        ],
        "stages": ["options", "recommend"],
    },
}

def _validate_seats() -> None:
    """Fail at IMPORT if any kind names a counselor that doesn't exist.

    Written because the first version of this file invented five counselors that were never on
    the roster (Warden, Muse, Scout, Prism, Vane). It surfaced as a bare `KeyError: 'Warden'`
    three stages into a live, billed run — after the model calls had already been paid for.
    A typo in a config dict should cost nothing and be caught instantly.
    """
    bad = []
    for kind, spec in KINDS.items():
        for seat in list(spec["seats"]) + [spec["critic"]]:
            if seat not in COUNSELORS:
                bad.append(f"{kind} -> {seat}")
    if bad:
        raise RuntimeError(
            "studio.KINDS names counselors that do not exist: " + ", ".join(bad) +
            f"\nreal roster: {', '.join(COUNSELORS)}")


_validate_seats()


# Words that signal a kind. Order matters: earlier entries win, and `code` must beat `write`
# because "write a script" is a code task, not a writing task.
_HINTS = [
    ("code",     r"\b(script|function|code|refactor|bug|test|cli|parser|api|module)\b"),
    ("build",    r"\b(page|html|dashboard|ui|site|widget|landing|interface|visuali[sz])\b"),
    ("decide",   r"\b(decide|choose|should we|which|recommend|versus|vs\.?|trade-?off|pick)\b"),
    ("research", r"\b(research|investigate|compare|analy[sz]e|find out|survey|landscape)\b"),
    ("write",    r"."),                                   # the catch-all
]


def classify(text: str) -> str:
    """Pick a kind from the task text. Cheap, deterministic, no model call.

    A model-based classifier would be marginally better and would cost a call per task on the
    hot path — so this is a regex that gets it right most of the time and can be overridden
    explicitly with `--kind`.
    """
    low = text.lower()
    for kind, pat in _HINTS:
        if re.search(pat, low):
            return kind
    return "write"


# ─────────────────────────────────────────────────────────── model plumbing

def _ask(seat: str, instruction: str, context: str = "") -> tuple[str, str]:
    """One model call as `seat`. Returns (text, mode); mode == 'template' means no backend."""
    spec = COUNSELORS.get(seat, COUNSELORS["Sage"])
    text, mode = llm(spec["provider"], spec["model"], persona_prompt(seat),
                     (context + "\n\n" if context else "") + instruction)
    return (strip_reasoning(text) if mode not in ("template", "budget") else text), mode


def _critique(kind: str, task: str, draft: str) -> dict:
    """Score a draft 0-10 against this kind's criteria and list concrete fixes.

    Returns {score, fixes[], verdict, mode}. A critic that cannot parse its own output is
    treated as a PASS rather than a fail — a broken critic must not silently block the loop
    forever, and the ledger records that it degraded.
    """
    spec = KINDS[kind]
    criteria = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(spec["criteria"]))
    instruction = (
        f"You are reviewing another counselor's work. Be exacting; you are the last check "
        f"before this reaches a human.\n\nTASK: {task}\n\nCRITERIA:\n{criteria}\n\n"
        f"DRAFT:\n---\n{draft[:6000]}\n---\n\n"
        "Reply with EXACTLY this shape and nothing else:\n"
        "SCORE: <0-10>\nFIXES:\n- <specific, actionable fix>\n- <another>\n"
        "If it scores 8+, write 'FIXES:\n- none'."
    )
    text, mode = _ask(spec["critic"], instruction)

    m = re.search(r"SCORE:\s*(\d+)", text)
    if not m:
        # Unparseable critic → don't deadlock the loop. Record it and let the draft through.
        return {"score": ACCEPT_SCORE, "fixes": [], "verdict": "critic-unparseable", "mode": mode}
    score = max(0, min(10, int(m.group(1))))
    fixes = [ln.strip("-• ").strip()
             for ln in text.split("FIXES:")[-1].splitlines()
             if ln.strip().startswith(("-", "•")) and "none" not in ln.lower()]
    return {"score": score, "fixes": [f for f in fixes if f][:5],
            "verdict": "accept" if score >= ACCEPT_SCORE else "revise", "mode": mode}


# ────────────────────────────────────────────────────── artifact validation

def _run_python(code: str) -> dict:
    """Actually execute generated Python in a subprocess and report what happened.

    This is the difference between "the model produced code" and "the code runs". It is a
    plain subprocess with a timeout, NOT a sandbox — generated code should be read before it
    is trusted, and `mindbot studio` says so in its output.
    """
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "artifact.py"
        f.write_text(code, encoding="utf-8")
        # Syntax first: a compile error is a clearer signal than a traceback.
        try:
            compile(code, str(f), "exec")
        except SyntaxError as e:
            return {"ran": False, "stage": "syntax", "error": f"line {e.lineno}: {e.msg}"}
        try:
            p = subprocess.run([sys.executable, str(f)], capture_output=True, text=True,
                               timeout=20, cwd=d)
        except subprocess.TimeoutExpired:
            return {"ran": False, "stage": "timeout", "error": "exceeded 20s"}

        # A CLI TOOL REFUSING TO RUN WITHOUT ITS ARGUMENTS IS CORRECT BEHAVIOUR.
        # First live run generated a perfectly good `dedupe.py <root>` and this checker marked
        # it FAIL, because running it bare made argparse exit 2 with a usage message. That is
        # the script working. Penalising it would train the studio to emit scripts that take no
        # arguments — i.e. worse scripts. So: argparse usage output means the module imported,
        # built its parser, and validated input. That is a pass, recorded distinctly.
        err = p.stderr or ""
        if p.returncode != 0 and re.search(r"^usage:", err, re.M):
            return {"ran": True, "stage": "cli", "exit": p.returncode,
                    "stdout": p.stdout[-400:],
                    "note": "CLI tool — loaded and correctly required its arguments"}
        return {"ran": p.returncode == 0, "stage": "exec", "exit": p.returncode,
                "stdout": p.stdout[-800:], "error": err[-800:]}


def _check_html(html: str) -> dict:
    """Structural check on generated HTML. Catches the failures that actually happen."""
    problems = []
    if "<html" not in html.lower() and "<div" not in html.lower():
        problems.append("no HTML elements found — the model probably replied in prose")
    for ext in ("http://", "https://"):
        if f'src="{ext}' in html or f'href="{ext}' in html:
            problems.append("references an external URL — the brief said self-contained")
            break
    opens = len(re.findall(r"<(?!/|!)([a-z][a-z0-9]*)", html, re.I))
    closes = len(re.findall(r"</([a-z][a-z0-9]*)", html, re.I))
    if opens and closes and abs(opens - closes) > opens * 0.5:
        problems.append(f"tags look unbalanced ({opens} open vs {closes} close)")
    return {"ran": not problems, "stage": "html", "error": "; ".join(problems)}


# ────────────────────────────────────────────────────────────── the engine

def run(task: str, kind: str = "", seat: str = "", rounds: int = MAX_ROUNDS,
        quiet: bool = False) -> dict:
    """Take one task through its full pipeline: stages → critique → revision → artifact.

    Returns a record of everything that happened, including every critique round — which is
    what gets ledgered and what makes the revision history provable.
    """
    kind = kind or classify(task)
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r} — one of {', '.join(KINDS)}")
    spec = KINDS[kind]
    seat = seat or spec["seats"][0]

    def say(msg):
        if not quiet:
            print(msg)

    ledger("studio_start", f"kind={kind} seat={seat} task={task[:70]}", "studio")
    say(f"\n  ┌─ STUDIO · {kind.upper()} · {seat}")
    say(f"  │  {task[:70]}")

    # ── stages: each one feeds the next, so later stages see earlier thinking ──────────
    context, degraded = "", False
    for stage in spec["stages"]:
        instr = _STAGE_PROMPTS[stage].format(task=task, ext=spec["ext"])
        out, mode = _ask(seat, instr, context)
        if mode in ("template", "budget"):
            degraded = True
        context += f"\n\n## {stage}\n{out}"
        say(f"  ├─ {stage:<10} {len(out):>5} chars  [{mode}]")

    draft = context.split(f"## {spec['stages'][-1]}\n", 1)[-1].strip()

    # ── critique → revise loop: the actual quality lever ───────────────────────────────
    #
    # KEEP THE BEST DRAFT, NOT THE LAST ONE. Measured on the first live run: a code artifact
    # scored 6/10, was revised against the critic's three fixes, and came back 4/10 — the
    # revision broke working code while "addressing feedback". Models over-correct. Shipping
    # whatever happened to come out of the final round throws away a better earlier version for
    # no reason, so the loop tracks the high-water mark and writes THAT.
    history = []
    best, best_score = draft, -1
    for rnd in range(1, max(1, rounds) + 1):
        crit = _critique(kind, task, draft)
        history.append({"round": rnd, "score": crit["score"], "fixes": crit["fixes"],
                        "verdict": crit["verdict"]})
        if crit["score"] > best_score:
            best, best_score = draft, crit["score"]
        ledger("studio_critique",
               f"round {rnd} score={crit['score']}/10 verdict={crit['verdict']} "
               f"fixes={len(crit['fixes'])}", f"critic:{spec['critic']}")
        kept = "  ← kept" if crit["score"] == best_score else ""
        say(f"  ├─ critique #{rnd}  {crit['score']}/10  {crit['verdict']}"
            + (f"  → {len(crit['fixes'])} fix(es)" if crit["fixes"] else "") + kept)

        if crit["verdict"] != "revise" or rnd == rounds or not crit["fixes"]:
            break
        fixes = "\n".join(f"- {f}" for f in crit["fixes"])
        revised, mode = _ask(seat,
            f"Revise your work. A reviewer scored it {crit['score']}/10 and asked for:\n{fixes}\n\n"
            f"Address every point, but do NOT rewrite what already works — a previous revision "
            f"scored LOWER by changing too much. Return the COMPLETE revised {spec['ext']}, not "
            f"a diff or a description of your changes.\n\nCURRENT:\n---\n{draft}\n---")
        if mode in ("template", "budget"):
            degraded = True
            break                                  # revising a template produces another template
        draft = strip_reasoning(revised)

    draft = best                                    # ship the high-water mark

    # ── artifact: extract, validate, write ────────────────────────────────────────────
    body = _extract(draft, spec["ext"])
    check = None
    if spec.get("executes"):
        check = _run_python(body)
        say(f"  ├─ execute     {'PASS' if check['ran'] else 'FAIL — ' + str(check.get('error'))[:60]}")
    elif spec.get("validates"):
        check = _check_html(body)
        say(f"  ├─ validate    {'PASS' if check['ran'] else 'FAIL — ' + str(check.get('error'))[:60]}")

    OUT.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", task.lower())[:44].strip("-") or "artifact"
    path = OUT / f"{now()[:10]}_{kind}_{slug}.{spec['ext']}"
    header = _header(kind, seat, spec["critic"], task, history, check, degraded, spec["ext"])
    path.write_text(header + body, encoding="utf-8")

    # Report the score of what we actually SHIPPED (the best round), not the last round —
    # otherwise a run that correctly discarded a bad revision would report the bad number.
    final = max((h["score"] for h in history), default=0)
    first = history[0]["score"] if history else 0
    ledger("studio_done",
           f"kind={kind} rounds={len(history)} {first}->{final}/10 "
           f"{'DEGRADED ' if degraded else ''}artifact={path.name}", "studio")
    say(f"  └─ {path.name}   {first}→{final}/10 over {len(history)} round(s)"
        + ("   [TEMPLATE MODE — scaffolding, not real work]" if degraded else ""))

    return {"kind": kind, "seat": seat, "critic": spec["critic"], "task": task,
            "rounds": history, "score": final, "improved": final - first,
            "artifact": str(path), "check": check, "degraded": degraded, "ok": True}


_STAGE_PROMPTS = {
    "draft":     "Write it. TASK: {task}\nNo preamble, no 'here is', no restating the task.",
    "questions": "TASK: {task}\nBefore answering: list the 4 questions that must be answered to "
                 "do this properly. Just the questions.",
    "answer":    "Now answer those questions and deliver the finished piece for: {task}",
    "plan":      "TASK: {task}\nIn 5 bullets: what does this need to do, and what is the one "
                 "case most likely to break it?",
    "implement": "Now write the complete {ext}. Output ONLY the {ext} in a single fenced code "
                 "block — no commentary before or after.",
    "design":    "TASK: {task}\nDescribe the visual approach in 4 bullets: layout, palette "
                 "(with hex codes), typography, and the one detail that makes it memorable.",
    "options":   "TASK: {task}\nList the 3 real options. For each: the strongest argument FOR, "
                 "and the thing that would kill it.",
    "recommend": "Now pick ONE and defend it. State the cost of being wrong.",
}


def _extract(text: str, ext: str) -> str:
    """Pull the artifact out of a model reply.

    Models wrap code in fences and add commentary no matter how firmly you ask them not to.
    For code/html we take the largest fenced block; for prose we keep everything.
    """
    if ext in ("md",):
        return text.strip() + "\n"
    blocks = re.findall(r"```(?:[a-zA-Z]*)\n(.*?)```", text, re.S)
    if blocks:
        return max(blocks, key=len).strip() + "\n"

    # NO COMPLETE FENCE. Usually means the reply was TRUNCATED mid-block — the model opened
    # ```python, ran out of tokens, and never closed it. Falling through to the raw text then
    # writes the literal fence into the artifact as line 1, and the syntax check fails on code
    # that is otherwise fine. Measured against a reasoning model, where long outputs truncate
    # routinely. So: if an opening fence exists, take everything after it and drop any stray
    # trailing fence.
    m = re.search(r"```[a-zA-Z]*\n", text)
    if m:
        tail = text[m.end():]
        tail = re.sub(r"\n?```\s*$", "", tail)
        return tail.strip() + "\n"
    return text.strip() + "\n"


def _header(kind, seat, critic, task, history, check, degraded, ext) -> str:
    """Provenance banner, commented for the artifact's own language.

    Every artifact carries how it was made — including its critique scores. An artifact you
    can't trace back to its review history is exactly the anonymous AI output this project
    exists to argue against.
    """
    lines = [
        f"MindBot Studio · {kind} · drafted by {seat} · reviewed by {critic}",
        f"task: {task}",
        f"rounds: " + " → ".join(f"{h['score']}/10" for h in history) if history else "rounds: none",
    ]
    if check:
        lines.append(f"check: {'PASS' if check['ran'] else 'FAIL — ' + str(check.get('error'))[:120]}")
    if degraded:
        lines.append("TEMPLATE MODE — no model backend was reachable. This is scaffolding, "
                     "not finished work.")
    lines.append(f"generated {now()} · verify: mindbot verify")

    if ext == "py":
        return '"""' + "\n" + "\n".join(lines) + "\n" + '"""' + "\n\n"
    if ext == "html":
        return "<!--\n" + "\n".join(lines) + "\n-->\n"
    return "<!--\n" + "\n".join(lines) + "\n-->\n\n"


def report(results: list[dict]) -> str:
    """Human summary of a studio session — what improved, and by how much."""
    if not results:
        return "no work done"
    avg = sum(r["score"] for r in results) / len(results)
    gained = sum(r["improved"] for r in results)
    rounds = sum(len(r["rounds"]) for r in results)
    passed = sum(1 for r in results if (r["check"] or {}).get("ran", True))
    # `+{gained}` printed "+-2" when revision made things worse. Since the loop now keeps the
    # best draft, `gained` can no longer go negative — but format it honestly regardless.
    delta = f"+{gained}" if gained > 0 else ("no gain" if gained == 0 else str(gained))
    return (f"{len(results)} artifact(s) · avg {avg:.1f}/10 · {delta} across "
            f"{rounds} critique round(s) · {passed}/{len(results)} passed validation")
