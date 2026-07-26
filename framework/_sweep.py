"""FULL CLI SWEEP — run every read-only command and report what actually works.

_full_audit.py checks subsystems. This checks the SURFACE: every command a user can type.
A subsystem can be perfectly healthy while the command that exposes it crashes on an
UnboundLocalError — which has happened in this codebase five times, and is exactly the class of
bug a subsystem audit cannot see.

Read-only by design. Commands that write, spend, or take minutes are listed and SKIPPED with a
reason rather than silently omitted — an untested command should be visible, not invisible.
"""
import re
import subprocess
import sys
from pathlib import Path

FW = Path(__file__).resolve().parent
CLI = [sys.executable, "-m", "mindbot_pipeline.cli"]

# Commands that cost money, mutate state, run for minutes, or block on a server.
SKIP = {
    "start": "starts a blocking web server",
    "serve": "starts a blocking web server",
    "yolo": "autonomous loop — writes drafts, spends",
    "autopilot": "spends; covered by _full_audit",
    "swarm": "spends; covered by test_swarm_mcp",
    "evolve": "self-modifies the repo",
    "reflect": "spends",
    "studio": "spends; covered by test_studio",
    "firm": "spends",
    "council": "spends",
    "meeting": "spends",
    "pulse": "spends; claims a task",
    "observe": "needs media + spends",
    "watch": "needs a video + spends",
    "say": "renders audio (slow); covered by the voice stress test",
    "voices": "safe — run explicitly below",
    "notarize": "appends an anchor",
    "stamp": "appends an anchor",
    "model": "mutates .env",
    "mod": "needs a subcommand — run explicitly below",
    "forge": "needs a subcommand",
    "modal": "network; run explicitly below",
    "review": "safe — run explicitly below",
    "backup": "writes a zip",
    "commit": "writes git history",
    "push": "writes to a remote",
    # Found by this sweep on its first run, and both are correct behaviour rather than bugs:
    # build-agent PROMPTS for consent and a name, so with stdin at /dev/null it exits 1; loop
    # blocks forever by design and hit the 180s timeout. An interactive or blocking command
    # cannot be smoke-tested by running it bare — it needs a driver, which is a different job.
    "build-agent": "interactive — prompts for consent + a name",
    "loop": "blocks by design (runs until stopped)",
}

# Commands worth running with explicit arguments.
EXPLICIT = [
    (["voices"], "the eleven"),
    (["mod", "list"], "installed mods"),
    (["forge", "list"], "packs + layers"),
    (["review"], "outbox drafts"),
    (["prove", "1"], "inclusion proof for seq 1"),
]


def commands() -> list[str]:
    src = (FW / "mindbot_pipeline" / "cli.py").read_text(encoding="utf-8")
    return sorted(set(re.findall(r'add_parser\(\s*"([a-z][a-z0-9-]*)"', src)))


def run(argv, timeout=180):
    try:
        p = subprocess.run(CLI + argv, cwd=FW, capture_output=True, text=True,
                           timeout=timeout, env=_utf8())
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def _utf8():
    import os
    e = dict(os.environ)
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def main():
    cmds = commands()
    ok = fail = skipped = 0
    failures = []

    print(f"\n  CLI SWEEP — {len(cmds)} commands registered\n")
    for c in cmds:
        if c in SKIP:
            skipped += 1
            continue
        code, out = run([c])
        # A command that needs arguments exits 2 with a usage message. That is CORRECT
        # behaviour, not a failure — the parser is doing its job.
        usage = "usage:" in out.lower() or "the following arguments are required" in out.lower()
        crashed = "Traceback" in out
        good = (code == 0 or (code == 2 and usage)) and not crashed
        if good:
            ok += 1
        else:
            fail += 1
            first = next((l for l in out.splitlines() if "Error" in l or "error" in l), "")
            failures.append((c, code, first.strip()[:100]))
            print(f"   FAIL  {c:<14} exit {code}  {first.strip()[:70]}")

    print(f"\n  bare invocation:  {ok} ok · {fail} failed · {skipped} skipped (side effects)\n")

    print("  explicit runs:")
    for argv, label in EXPLICIT:
        code, out = run(argv)
        crashed = "Traceback" in out
        mark = "ok  " if code == 0 and not crashed else "FAIL"
        if mark == "FAIL":
            fail += 1
            failures.append((" ".join(argv), code, out.splitlines()[-1][:100] if out else ""))
        print(f"   {mark}  mindbot {' '.join(argv):<16} {label}")

    print(f"\n  SKIPPED (side effects — not untested, just not here):")
    for c, why in sorted(SKIP.items()):
        print(f"     {c:<12} {why}")

    print(f"\n  {'=' * 62}")
    print(f"  RESULT: {ok + len(EXPLICIT) - sum(1 for f in failures if ' ' in f[0])} passing, "
          f"{fail} failing, {skipped} skipped")
    print(f"  {'=' * 62}\n")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
