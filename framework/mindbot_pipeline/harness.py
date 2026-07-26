"""THE CODING HARNESS — counselors get hands.

opencode/Claude-Code-style agentic loop, built into the framework core:
the model receives TOOLS (read, write, list, search, run, done) and iterates —
read → think → edit → run tests → finish — up to MAX_STEPS, every step tracked.

Design choices that make this OURS:
- JSON tool protocol, not native function-calling — works on ANY backend, including
  free OpenRouter models and local ollama. The harness runs on a $0 budget.
- Jail: all paths confined to the repo; .env and .git are unreadable/unwritable;
  run_command is whitelisted (python/pytest/git-read-only). No network, no shell tricks.
- Every step → trails.jsonl + ledger. The diff is the deliverable; tests are the judge.
- Red tests at the end → touched files auto-reverted (git checkout). Honest failure
  beats silent breakage.

Extend: add a tool -> write a t_* fn (takes args dict, returns str) and register it
in TOOLS, then document its JSON shape in PROTOCOL so the model knows to call it.
Widen what run_command may execute -> add a prefix to RUN_WHITELIST. Tighten the jail
-> add to FORBIDDEN. The loop in code_task() is backend-agnostic; do not add native
function-calling — the JSON protocol is what keeps it running on $0 models.

CLI: python -m mindbot_pipeline.cli code "<task>" [--seat Forge] [--steps 12]
"""

import json
import re
import subprocess

from .collaboration import PIPE_DIR, ROOT, ledger
from .counselors import COUNSELORS, persona_prompt
from .familiars import FAMILIARS, track
from .models import llm

MAX_OUT = 4000          # chars of tool output fed back per step
FORBIDDEN = (".env", ".git")
RUN_WHITELIST = ("python", "py", "git status", "git diff", "git log", "pip show")


def _safe(path: str):
    # The jail. resolve() collapses ../ so a crafted path can't climb out of ROOT;
    # the prefix check then rejects anything that still lands outside the repo.
    p = (ROOT / path).resolve()
    if not str(p).startswith(str(ROOT.resolve())):
        raise ValueError(f"path escapes repo: {path}")
    if any(f in str(p).lower() for f in FORBIDDEN):
        raise ValueError(f"forbidden path: {path}")
    return p


def t_read(args):
    p = _safe(args["path"])
    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    s, e = int(args.get("start", 1)), int(args.get("end", min(len(lines), 200)))
    return "\n".join(f"{i+1}: {l}" for i, l in enumerate(lines[s-1:e], s-1))


def t_write(args):
    p = _safe(args["path"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(args["content"], encoding="utf-8", newline="\n")
    return f"wrote {len(args['content'])} chars to {args['path']}"


def t_list(args):
    p = _safe(args.get("path", "."))
    items = sorted(p.iterdir())
    return "\n".join(("d " if i.is_dir() else "f ") + i.name for i in items[:80])


def t_search(args):
    pat, hits = args["pattern"], []
    for f in ROOT.rglob(args.get("glob", "*.py")):
        if any(x in str(f) for x in (".git", "venv", "__pycache__", "node_modules")):
            continue
        try:
            for n, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if re.search(pat, line):
                    hits.append(f"{f.relative_to(ROOT)}:{n}: {line.strip()[:100]}")
                if len(hits) >= 25:
                    return "\n".join(hits)
        except OSError:
            continue
    return "\n".join(hits) or "no matches"


def t_run(args):
    cmd = args["command"].strip()
    if not any(cmd.startswith(w) for w in RUN_WHITELIST):
        return f"REFUSED: only {RUN_WHITELIST} allowed (no network, no shell tricks)"
    r = subprocess.run(cmd, shell=True, cwd=str(PIPE_DIR), capture_output=True,
                       text=True, timeout=180)
    return f"exit={r.returncode}\n{(r.stdout + r.stderr)[-MAX_OUT:]}"


TOOLS = {"read_file": t_read, "write_file": t_write, "list_dir": t_list,
         "search": t_search, "run_command": t_run}

PROTOCOL = """You are coding INSIDE the MINDBOTZ repo via tools. Respond with EXACTLY ONE
JSON object per turn, nothing else, in a ```json fence:
{"tool": "read_file",  "args": {"path": "framework/...", "start": 1, "end": 120}}
{"tool": "write_file", "args": {"path": "...", "content": "FULL new file content"}}
{"tool": "list_dir",   "args": {"path": "framework/mindbot_pipeline"}}
{"tool": "search",     "args": {"pattern": "def pulse", "glob": "*.py"}}
{"tool": "run_command","args": {"command": "python -m unittest discover tests"}}
{"tool": "done",       "args": {"summary": "what you changed and proof it works"}}
Rules: read before you write. write_file replaces the WHOLE file. Run the tests
before done. Never touch .env or .git. If blocked, finish with done and say why."""


def code_task(task: str, seat: str = "Forge", max_steps: int = 12,
              model: str | None = None) -> dict:
    """The agentic loop. Returns {ok, steps, summary, touched}.

    model: optional override of the seat's default model — any OpenRouter slug,
    OpenAI model id, or local ollama tag. Lets an Operator point Forge at a
    dedicated coder (e.g. moonshotai/kimi-k2.7-code) for a single run.
    """
    spec = dict(COUNSELORS.get(seat, COUNSELORS["Forge"]))
    if model:
        spec["model"] = model
    fam = FAMILIARS.get(seat, FAMILIARS["Forge"])
    sysp = persona_prompt(seat) + "\n\n" + PROTOCOL
    convo = f"TASK: {task}\nRepo root is the MINDBOTZ folder. Begin."
    touched, transcript = [], []
    last_write, repeat_writes = None, 0
    ledger("harness_start", f"{seat}: {task[:90]}", seat)
    for step in range(1, max_steps + 1):
        left = max_steps - step
        convo += f"\nSTEPS LEFT: {left}." + (
            " You MUST run_command the tests NOW, then call done." if left <= 3 else "")
        # mode = which backend actually answered (sonic/openrouter/cloud/local/template);
        # surfaced in the return dict for the ledger so a $0 fallback isn't mistaken for a paid run.
        text, mode = llm(spec["provider"], spec["model"], sysp, convo)
        # Greedy {.*} grabs the outer JSON even when a weak model wraps it in prose; re.S
        # so the object can span lines. Fences are stripped first since they break json.loads.
        m = re.search(r"\{.*\}", text.replace("```json", "").replace("```", ""), re.S)
        if not m:
            convo += "\nSYSTEM: no JSON found. Reply with exactly one JSON tool call."
            continue
        try:
            call = json.loads(m.group(0))
            tool, args = call.get("tool"), call.get("args", {})
        except (json.JSONDecodeError, AttributeError):
            convo += "\nSYSTEM: invalid JSON. One object, one tool call."
            continue
        track(fam["name"], fam["glyph"], f"harness step {step}", f"{tool}: {str(args)[:80]}")
        if tool == "done":
            summary = args.get("summary", "")
            ok = _verify_and_seal(seat, task, touched, summary)
            return {"ok": ok, "steps": step, "summary": summary[:400],
                    "touched": touched, "mode": mode}
        # Loop-breaker + auto-seal: the harness supplies the discipline weak models
        # lack. Two repeated writes to the same file → harness runs the tests itself;
        # green → auto-seal (deterministic scaffolding beats wandering).
        if tool == "write_file":
            if args.get("path") == last_write:
                repeat_writes += 1
            else:
                last_write, repeat_writes = args.get("path"), 0
            if repeat_writes >= 2:
                TOOLS["write_file"](args)  # honor the final version, once
                if args.get("path") not in touched:
                    touched.append(args["path"])
                ok = _verify_and_seal(seat, task, touched, "auto-sealed after write-loop")
                return {"ok": ok, "steps": step, "summary":
                        f"auto-sealed: model looped on {args.get('path')}; harness ran tests "
                        f"({'GREEN — kept' if ok else 'RED — reverted'})",
                        "touched": touched, "mode": mode + "+autoseal"}
        fn = TOOLS.get(tool)
        if not fn:
            result = f"unknown tool {tool!r}"
        else:
            try:
                result = fn(args)
                if tool == "write_file" and args.get("path") not in touched:
                    touched.append(args["path"])
                    result += "  [SAVED — do not write this file again unless changing it]"
            except Exception as e:  # noqa: BLE001 — harness must not crash mid-loop
                result = f"TOOL ERROR: {e}"
        transcript.append((tool, str(args)[:120], result[:200]))
        convo += f"\nYOU CALLED: {tool}({json.dumps(args)[:300]})\nRESULT:\n{result[:MAX_OUT]}\nNext JSON:"
    # Out of steps without a done call: assume incomplete work, revert rather than
    # leave a half-finished edit on disk. Same honest-failure contract as red tests.
    ledger("harness_maxsteps", f"{seat}: ran out of steps on {task[:60]}", seat)
    _revert(touched)
    return {"ok": False, "steps": max_steps, "summary": "max steps — touched files reverted",
            "touched": touched, "mode": "n/a"}


def _verify_and_seal(seat, task, touched, summary):
    """Tests are the judge. Green → keep + ledger. Red → revert + honest failure."""
    r = subprocess.run("python -m unittest discover tests", shell=True,
                       cwd=str(PIPE_DIR), capture_output=True, text=True, timeout=300)
    if r.returncode == 0:
        ledger("harness_done", f"{seat}: {task[:60]} | files: {touched} | tests GREEN", seat)
        return True
    _revert(touched)
    ledger("harness_reverted", f"{seat}: tests RED after {task[:60]} — reverted {touched}", seat)
    return False


def _revert(touched):
    for f in touched:
        subprocess.run(f'git checkout -- "{f}"', shell=True, cwd=str(ROOT),
                       capture_output=True, text=True)
        subprocess.run(f'git clean -f -- "{f}"', shell=True, cwd=str(ROOT),
                       capture_output=True, text=True)
