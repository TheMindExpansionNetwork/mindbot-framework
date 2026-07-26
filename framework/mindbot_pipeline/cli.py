"""CLI: the Operator's handle and the cron's entry point — and the front door of
the whole framework. Start reading the codebase HERE.

Extend: add a command -> (1) `sub.add_parser("name", ...)` in main(); (2) an
`elif args.cmd == "name":` branch. Heavy logic stays in sibling modules — keep
branches thin (lazy-import + call + print). Add a counselor -> counselors.COUNSELORS;
add a model provider -> models.py (+ a keymap row in the `auth` branch).

=== LEARNING NOTE (this is a learning project — see docs/LEARNING.md) ===
Every command is two small pieces, and adding one is the easiest way to learn the
codebase:
  1) REGISTER it: in main(), add `sub.add_parser("yourcmd", help="...")`
     (add `.add_argument(...)` lines if it takes arguments).
  2) HANDLE it: add an `elif args.cmd == "yourcmd":` branch that calls your code.
That's the entire pattern — `mindbot yourcmd` now works. Run `cli -h` to see them all.
Each command is self-documenting via `cli <cmd> -h`. The heavy logic lives in
sibling modules (nucleus=the loop, harness=coding, models=the router); cli.py just
wires them to words a human types.

  python -m mindbot_pipeline.cli pulse [--agent Vanguard]   one heartbeat
  python -m mindbot_pipeline.cli yolo [--rounds N]          autonomous, refills itself
  python -m mindbot_pipeline.cli code "<task>" --seat Forge the coding harness
  python -m mindbot_pipeline.cli play                       the sci-fi console
  python -m mindbot_pipeline.cli doctor                     verify the setup
  ... (cli -h for the full list)
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mindbot_pipeline.collaboration import (COLLAB, DASH_STATE, DATASET_OUT,
                                            HANDOFF_PATH, LEDGER_PATH, PIPE_DIR,
                                            ROOT, STATE_PATH, TODO_PATH,
                                            load_state, read_tasks)
from mindbot_pipeline.counselors import COUNSELORS
from mindbot_pipeline.nucleus import OUTBOX, morning_report, pulse


def cmd_doctor():
    """Loud diagnostics: what works, what's missing, what the Operator must do."""
    checks = []

    def ck(name, ok, fix=""):
        checks.append((name, ok, fix))

    ck("python >= 3.10", sys.version_info >= (3, 10), "install Python 3.10+")
    ck(f"workspace root ({ROOT.name})", ROOT.exists())
    ck("state.json", STATE_PATH.exists(), "restore from git — it is the single source of truth")
    ck("BIG_TODO_LIST.md", TODO_PATH.exists(), "create it or copy the template from collaboration/")
    ck("handoff notes", HANDOFF_PATH.exists(), "created automatically on first pulse")
    ck("dataset manifest", (DATASET_OUT / "MANIFEST.json").exists(),
       "run dataset/generator/generate_dataset.py")
    ck("skills dir", (PIPE_DIR / "skills").exists(), "git restore framework/skills")
    tasks = read_tasks()
    ck(f"TODO parses ({len(tasks)} tasks)", bool(tasks) or not TODO_PATH.exists())
    brains = [k for k in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
                          "XAI_API_KEY", "DEEPSEEK_API_KEY", "GOOGLE_API_KEY",
                          "MISTRAL_API_KEY") if os.environ.get(k)]
    ck(f"model backend ({', '.join(brains) if brains else 'none — template mode'})",
       True if brains else False,
       "set OPENROUTER_API_KEY (one key = all 11 counselors) or start Ollama")
    # Presence is not health: stale env keys are this machine's chronic disease.
    if os.environ.get("OPENROUTER_API_KEY"):
        import urllib.request
        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/key",
                headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
            with urllib.request.urlopen(req, timeout=15) as r:
                ck("OPENROUTER_API_KEY is LIVE", r.status == 200)
        except Exception:
            ck("OPENROUTER_API_KEY is LIVE", False,
               "key is stale/revoked — paste a fresh one from openrouter.ai/keys "
               "($env:OPENROUTER_API_KEY='sk-or-...')")
    state = load_state() if STATE_PATH.exists() else {}
    ck(f"focus block ('{state.get('focus', {}).get('mission', '')[:50]}…')",
       bool(state.get("focus")))
    width = max(len(c[0]) for c in checks) + 2
    # exit non-zero on any failed check so cron / CI can gate on `doctor`.
    bad = 0
    for name, ok, fix in checks:
        mark = "✓" if ok else "✗"
        line = f" {mark} {name:<{width}}"
        if not ok:
            bad += 1
            line += f"→ {fix}"
        print(line)
    print(f"\n{'all clear — the loop is ready' if not bad else f'{bad} issue(s) — fix the ✗ lines above'}")
    return 0 if not bad else 1


def cmd_outbox():
    drafts = sorted(OUTBOX.glob("*.md")) if OUTBOX.exists() else []
    if not drafts:
        print("outbox empty — nothing awaits approval. The council is either idle or honest.")
        return
    print(f"{len(drafts)} draft(s) awaiting the Operator (agent proposes, operator disposes):\n")
    for p in drafts:
        first = p.read_text(encoding="utf-8").splitlines()[0][:90]
        print(f"  {p.name}\n    {first}")
    print("\nreview each, then send manually or delete. Nothing here transmits itself.")


def cmd_ledger(n):
    if not LEDGER_PATH.exists():
        print("ledger empty — no events yet.")
        return
    lines = LEDGER_PATH.read_text(encoding="utf-8").splitlines()[-n:]
    for line in lines:
        try:
            e = json.loads(line)
            print(f"{e['ts']}  [{e['agent']:<9}] {e['event']:<16} {e['detail'][:90]}")
        except json.JSONDecodeError:
            continue


def cmd_recall(word):
    """Search the swarm's memory: semantic index first, then handoffs/ledger/TODO grep."""
    try:
        from mindbot_pipeline.memory import search
        sem = search(word, k=3)
        for r in sem:
            print(f"[memory {r['score']}] {r['text'][:110]}")
    except Exception:
        pass
    word_l = word.lower()
    hits = 0
    for label, path in (("handoff", HANDOFF_PATH), ("todo", TODO_PATH)):
        if path.exists():
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if word_l in line.lower():
                    print(f"[{label}:{i}] {line.strip()[:120]}")
                    hits += 1
    if LEDGER_PATH.exists():
        for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines():
            if word_l in line.lower():
                try:
                    e = json.loads(line)
                    print(f"[ledger] {e['ts']} {e['event']}: {e['detail'][:100]}")
                    hits += 1
                except json.JSONDecodeError:
                    continue
    print(f"\n{hits} memory hit(s) for {word!r}" if hits else f"no memory of {word!r} — maybe it was a dream. Check lore/dream_log.")


def cmd_evaluate(path_str):
    """Mechanical scorer for model outputs — the format half of the gold gate.

    Accepts the gold_eval/*.md produced by train_mindbot_v1.py, or any .jsonl with
    a 'completion' field. Checks the trainable disciplines a machine can check:
    tag structure, transmission claims, NEED honesty, degenerate length. The
    judgment half (canon-true? alive?) stays with the Operator — by design.
    """
    import re as _re
    p = Path(path_str)
    if not p.exists():
        print(f"no such file: {p}")
        return 1
    if p.suffix == ".jsonl":
        outputs = [json.loads(l).get("completion", "") for l in p.open(encoding="utf-8")]
    else:
        outputs = _re.findall(r"\*\*MODEL:\*\*\n```\n(.*?)\n```", p.read_text(encoding="utf-8"), _re.S)
    if not outputs:
        print("no model outputs found in file")
        return 1
    rows, passed = [], 0
    for i, o in enumerate(outputs):
        checks = {
            "ends_reasoning": "<end_working_out>" in o,
            "has_solution": "<SOLUTION>" in o and "</SOLUTION>" in o,
            "no_transmit_claim": not any(b in o.lower() for b in
                ("i have sent", "posted to", "payment complete", "emailed ")),
            "not_degenerate": 40 < len(o.split()) < 1600,
            "need_not_spammed": o.count("[NEED:") <= 3,
        }
        ok = all(checks.values())
        passed += ok
        rows.append((i, ok, [k for k, v in checks.items() if not v]))
    for i, ok, fails in rows:
        print(f"  {'✓' if ok else '✗'} output {i:02d}" + (f"  failed: {', '.join(fails)}" if fails else ""))
    pct = 100 * passed / len(rows)
    print(f"\nFORMAT GATE: {passed}/{len(rows)} pass ({pct:.0f}%). "
          + ("Mechanically promotable — now do the human half: read them." if pct >= 80
             else "Below 80% — do not promote; the failures define tomorrow's curation."))
    return 0 if pct >= 80 else 1


def cmd_shards():
    shards = ROOT / "collaboration" / "SHARDS.md"
    if not shards.exists():
        shards = COLLAB / "SHARDS.md"
    if not shards.exists():
        print("no SHARDS.md found")
        return
    open_n = 0
    for line in shards.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("- [ ]"):
            open_n += 1
            print(f"  ◇ {line.strip()[6:][:110]}")
    print(f"\n{open_n} open shard(s). 5–30 minutes each. Your work retrains the Mind; your name goes in the credits.")


def cmd_missions(start_id=None):
    """Mission arcs: named goals bundling TODO tasks. Progress from the live board."""
    mp = COLLAB / "missions.json"
    if not mp.exists():
        mp = ROOT / "collaboration" / "missions.json"
    data = json.loads(mp.read_text(encoding="utf-8"))
    todo_text = TODO_PATH.read_text(encoding="utf-8") if TODO_PATH.exists() else ""
    for m in data["missions"]:
        # presence of the mission tag in the TODO file == "this mission has been started".
        seeded = m["tag"] in todo_text
        if start_id and m["id"] == start_id and not seeded:
            from mindbot_pipeline.collaboration import add_task
            for t in m["tasks"]:
                add_task(t, "MissionControl")
            print(f"★ MISSION STARTED: {m['name']} — {len(m['tasks'])} tasks seeded to the board.")
            seeded = True
            todo_text = TODO_PATH.read_text(encoding="utf-8")
        done = todo_text.count(f"- [x] {m['tag']}") + len(
            [l for l in todo_text.splitlines() if m["tag"] in l and l.strip().startswith("- [x]")])
        total = len(m["tasks"])
        done = min(done, total)  # cap: the two counts above can overlap-count a line
        bar = "█" * done + "░" * (total - done)
        status = "complete ✦" if done == total and seeded else ("active" if seeded else "not started — `missions start " + m["id"] + "`")
        print(f"\n  {m['name']:<14} [{bar}] {done}/{total}  {status}")
        print(f"    goal: {m['goal']}")
        print(f"    lore: \"{m['lore']}\"")
    print()


def cmd_skill_new(name, desc):
    """The coding kata: scaffold a skill, register its test-run task. Build → test → active."""
    import re as _re
    slug = "-".join(_re.findall(r"[a-z0-9]+", name.lower())) or "new-skill"
    d = PIPE_DIR / "skills" / slug
    if d.exists():
        print(f"skill '{slug}' already exists")
        return 1
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {slug}\ndescription: {desc or '[NEED: one-line trigger]'}\n"
        f"status: draft\n---\n\n# {slug}\n\n## When to use\n[NEED]\n\n## Inputs it expects\n"
        f"[NEED]\n\n## Steps\n1. [NEED — mechanical, reproducible]\n2. Every step that could "
        f"transmit: **STOP — outbox, human sends.**\n\n## Output contract\n[NEED: files + "
        f"ledger line + handoff]\n\n## Failure modes\n[NEED: loud, never silent]\n",
        encoding="utf-8")
    from mindbot_pipeline.collaboration import add_task, ledger
    add_task(f"[M:skill-garden] Test-run skill '{slug}' and promote draft → active", "skill-forge")
    ledger("skill_scaffolded", slug, "skill-forge")
    print(f"⚒ skill scaffolded → skills/{slug}/SKILL.md (status: draft)")
    print(f"  fill the [NEED]s, test-run it, flip status: active. Task registered on the board.")
    return 0


def cmd_employees():
    """Roster of the EMPLOYEES — humans-grade crew (not counselor seats). Auto-discovered
    from lore/*.md files marked 'Employee #'. J1MSKY runs the metal; D0Z3R runs the night."""
    import re as _re
    from mindbot_pipeline.collaboration import ROOT
    lore = ROOT / "lore"
    rows, found = [], []
    for f in sorted(lore.glob("*.md")) if lore.exists() else []:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        # prefer the "# NAME — Employee #N" header; fall back to a bare "Employee #N"
        # (then the filename stems in for the name).
        m = _re.search(r"#\s*([A-Z0-9]+)\s+—\s+Employee #(\d+)", txt)
        if not m:
            m = _re.search(r"Employee #(\d+)", txt)
            if m:
                name = f.stem
                num = m.group(1)
            else:
                continue
        else:
            name, num = m.group(1), m.group(2)
        glyph = (_re.search(r"\*\*Glyph:\*\*\s*(\S+)", txt) or [None, "•"])[1]
        color = (_re.search(r"\*\*Color:\*\*\s*([^`\n]+)", txt) or [None, ""])[1].strip()
        fam = _re.search(r"\*\*Familiar:\*\*\s*(.+)", txt)
        fam = fam.group(1).split("—")[0].replace("**", "").strip() if fam else ""
        found.append((int(num), name, glyph, color, fam, f.name))
    found.sort()
    from mindbot_pipeline import tui
    if not found:
        print("no employees yet — hire one: drop a lore/<NAME>.md marked 'Employee #N'")
        return
    for num, name, glyph, color, fam, fn in found:
        rows.append(f"#{num:03d}  {glyph} {name:<8} {fam}")
    print(tui.panel("◉ EMPLOYEES — the crew", rows, tui.CYAN, 66))
    print(f"  {tui.DIM}counselors propose · employees run the metal · operators dispose{tui.R}")


def cmd_trails(n):
    from mindbot_pipeline.familiars import trails_tail
    rows = trails_tail(n)
    if not rows:
        print("no tracks yet — the ecosystem hasn't moved. Run `play` or `pulse`.")
        return
    print(f"\n  ECOSYSTEM TRAILS — last {len(rows)} footprints\n")
    for r in rows:
        print(f"  {r['ts'][11:]} {r['glyph']} {r['actor']:<8} {r['action']:<24} {r['detail'][:70]}")
    print("\n  every worker leaves tracks. the ground remembers.\n")


def main():
    ap = argparse.ArgumentParser(prog="mindbot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    # NB: the parser handles (p/pl/pm/ps…) below are reused freely — each is only
    # touched right after its add_parser, so the names colliding is harmless.
    p = sub.add_parser("pulse", help="one heartbeat: claim a task, work it, hand off")
    p.add_argument("--agent", default=None, help="force a counselor (default: route by domain)")
    p.add_argument("--dry-run", action="store_true")
    sub.add_parser("report", help="write the morning report")
    sub.add_parser("status", help="print tracker state")
    sub.add_parser("council", help="print the 11 counselors")
    sub.add_parser("doctor", help="environment + structure diagnostics")
    sub.add_parser("outbox", help="list drafts awaiting human approval")
    pl = sub.add_parser("ledger", help="tail the ledger")
    pl.add_argument("-n", type=int, default=20)
    pr = sub.add_parser("recall", help="search handoffs + ledger + TODO")
    pr.add_argument("word")
    pe = sub.add_parser("evaluate", help="mechanical format gate for model outputs (gold_eval md or jsonl)")
    pe.add_argument("path")
    sub.add_parser("shards", help="list open community micro-tasks")
    sub.add_parser("play", help="THE SWITCHBOARD — boot intro + live talk with any counselor")
    pm = sub.add_parser("missions", help="mission arcs with live progress")
    pm.add_argument("action", nargs="?", default=None, help="'start'")
    pm.add_argument("mission_id", nargs="?", default=None)
    ps = sub.add_parser("skill", help="forge a new skill: skill new <name> [desc]")
    ps.add_argument("action")
    ps.add_argument("name")
    ps.add_argument("desc", nargs="?", default="")
    pt = sub.add_parser("trails", help="the ecosystem's footprints (familiar + counselor tracks)")
    pt.add_argument("-n", type=int, default=20)
    pc = sub.add_parser("code", help="THE CODING HARNESS — a counselor reads/writes/runs code agentically")
    pc.add_argument("task")
    pc.add_argument("--seat", default="Forge")
    pc.add_argument("--steps", type=int, default=12)
    pc.add_argument("--model", default=None,
                    help="override the seat's model (e.g. moonshotai/kimi-k2.7-code). "
                         "OpenRouter slug, OpenAI model id, or local ollama tag.")
    pl = sub.add_parser("loop", help="AUTONOMOUS DAEMON — pulse on repeat until idle/paused (it runs itself)")
    pl.add_argument("--rounds", type=int, default=0, help="0 = until board idle")
    pl.add_argument("--interval", type=float, default=0.0, help="seconds between pulses")
    pl.add_argument("--agent", default=None)
    pm = sub.add_parser("meeting", help="COUNCIL MEETING — 3 seats deliberate, minutes to outbox")
    pm.add_argument("topic")
    pm.add_argument("--seats", default=None, help="comma list, e.g. Sage,Forge,Spark")
    pm.add_argument("--model", default=None)
    py = sub.add_parser("yolo", help="YOLO MODE — autonomous loop that refills itself & never stops (outbox-gated)")
    py.add_argument("--rounds", type=int, default=40)
    py.add_argument("--interval", type=float, default=0.0)
    psw = sub.add_parser("swarm", help="LAUNCH SWARM — N councilors pulse CONCURRENTLY against the board")
    psw.add_argument("--workers", type=int, default=3, help="how many councilors pulse in parallel")
    psw.add_argument("--rounds", type=int, default=0, help="total pulses across the swarm (0 = until idle)")
    psw.add_argument("--idle-stop", type=int, default=3, help="stop after this many empty pulses")
    psw.add_argument("--interval", type=float, default=0.0, help="optional pause between a worker's pulses")
    sub.add_parser("health", help="AUTONOMOUS SELF-CHECK — ready to run unattended? board / errors / fund")
    pap = sub.add_parser("autopilot", help="ONE-COMMAND AUTONOMY — health -> swarm -> report (cost-safe)")
    pap.add_argument("--rounds", type=int, default=6, help="total pulses across the swarm")
    pap.add_argument("--workers", type=int, default=3, help="concurrent councilors")
    pev = sub.add_parser("evolve", help="🧬 SELF-IMPROVE — the system writes + tests + proposes its OWN code")
    pev.add_argument("--iterations", type=int, default=1, help="how many self-improvement attempts")
    pev.add_argument("--seat", default="Forge", help="which counselor codes")
    pev.add_argument("--dry-run", action="store_true", help="prove the loop but revert any change")
    pev.add_argument("task", nargs="?", default=None, help="a specific coding task (blank = a safe self-task)")
    prf = sub.add_parser("reflect", help="🧭 SELF-DIRECTION — review progress, propose the next high-leverage tasks")
    prf.add_argument("--propose", type=int, default=3, help="how many next tasks to propose")
    sub.add_parser("attest", help="🔐 PROOF-OF-AUTONOMY — cryptographic compliance attestation (+ a cert)")
    sub.add_parser("verify", help="🔐 verify the tamper-evident ledger chain is intact")
    pnt = sub.add_parser("notarize", help="🔏 NOTARY — anchor the merkle root (commit+push = third-party proof)")
    pnt.add_argument("--audit", action="store_true", help="re-check today's history against every published anchor")
    pnt.add_argument("--note", default="", help="label for this anchor")
    ppv = sub.add_parser("prove", help="🧾 inclusion proof for ONE action — verifiable without revealing the rest")
    ppv.add_argument("seq", type=int, help="the ledger seq to prove")
    pst = sub.add_parser("start", help="🚀 START HERE — launch the UI (setup if needed, then Mission Control)")
    pst.add_argument("--port", type=int, default=8080)
    pst.add_argument("--no-browser", action="store_true", help="don't open a browser window")
    sub.add_parser("budget", help="💰 BUDGET — the hard spend ceiling the agent cannot cross")
    pwa = sub.add_parser("whoami", help="🪞 WHOAMI — what I am, what I can do, what I've done, what I can't")
    pwa.add_argument("--json", action="store_true", help="machine-readable self-model")
    psay = sub.add_parser("say", help="🔊 SAY — local CPU text-to-speech (Inflect, 16 MB, ~10x realtime)")
    psay.add_argument("text", nargs="?", default="", help="what to say")
    psay.add_argument("--file", default="", help="read a text/markdown file aloud instead")
    psay.add_argument("--out", default="", help="output .wav path")
    psay.add_argument("--speed", type=float, default=1.0)
    psay.add_argument("--seed", type=int, default=7, help="deterministic by default")
    psay.add_argument("--check", action="store_true", help="is Inflect installed and loadable?")
    psay.add_argument("--as", dest="as_", default="", help="speak as a counselor (mindbot voices)")
    psay.add_argument("--variation", type=float, default=None)
    p20 = sub.add_parser("twenty", help="🎯 TWENTY — 20 questions vs an opponent that provably cannot cheat")
    p20.add_argument("action", nargs="?", default="play",
                     choices=["play", "new", "ask", "guess", "status", "audit"])
    p20.add_argument("text", nargs="*", default=[], help="your question or guess")
    p20.add_argument("--game", default="", help="game id (default: the most recent)")
    p20.add_argument("--category", default="", help="e.g. 'an animal'")
    pme = sub.add_parser("me", help="🫵 ME — your own MindBot: the eleventh seat, the one you talk to")
    pme.add_argument("--create", action="store_true", help="make one")
    pme.add_argument("--name", default="", help="what to call it")
    pme.add_argument("--vibe", default="", help="warm | dry | eager | grave | feral | deadpan")
    pme.add_argument("--voice", default="", help="a kokoro voice id (mindbot voices)")
    pme.add_argument("--pet", default="", help="its runner")
    pme.add_argument("--motto", default="", help="one line it lives by")
    pme.add_argument("--overwrite", action="store_true", help="replace the one you have")
    ppt = sub.add_parser("pets", help="🦉 PETS — every counselor has a runner; their stats come from the ledger")
    ppt.add_argument("who", nargs="?", default="", help="one counselor, for detail")
    ppt.add_argument("--feed", default="", help="how do I level this one?")
    pvo = sub.add_parser("voices", help="🎭 VOICES — the eleven, and their signatures")
    pvo.add_argument("--introduce", nargs="?", const="ALL", default="",
                     help="render introductions (blank = all, or a name)")
    pob = sub.add_parser("observe", help="👁️  OBSERVE — describe images/audio and make every observation provable")
    pob.add_argument("folder", help="folder of images and/or audio")
    pob.add_argument("--json", action="store_true", help="print the catalog as JSON")
    pwa = sub.add_parser("watch", help="🎥 WATCH — sample a video every N seconds; every frame provable, quiet ones too")
    pwa.add_argument("video", help="path to a video file")
    pwa.add_argument("--every", type=int, default=60, help="seconds between sampled frames (default 60)")
    pwa.add_argument("--limit", type=int, default=0, help="stop after N frames (0 = all)")
    pwa.add_argument("--json", action="store_true", help="print the log as JSON")
    pfg = sub.add_parser("forge", help="⚒️  FORGE — create mods, and total-conversion packs (crew/look/rules/quests)")
    pfg.add_argument("action", choices=["mod", "pack", "install", "uninstall", "list", "check"])
    pfg.add_argument("target", nargs="?", default="", help="a description (mod) or a name (pack)")
    pmdl = sub.add_parser("modal", help="🛰️  MODAL — your own multimodal endpoint (text + image + audio)")
    pmdl.add_argument("action", nargs="?", default="check", choices=["check", "models", "ask", "see", "hear"])
    pmdl.add_argument("arg", nargs="?", default="", help="prompt, or a path to an image/audio file")
    pstu = sub.add_parser("studio", help="🎬 STUDIO — typed pipelines + a critique loop: draft → review → revise → artifact")
    pstu.add_argument("task", nargs="?", default="", help="what to make (blank = pull from the board)")
    pstu.add_argument("--kind", default="", help="write | research | code | build | decide (default: auto)")
    pstu.add_argument("--seat", default="", help="which counselor drafts it")
    pstu.add_argument("--rounds", type=int, default=3, help="max critique rounds")
    pstu.add_argument("--batch", type=int, default=0, help="take N tasks off the board instead")
    pstm = sub.add_parser("stamp", help="🏷️  STAMP — mint a verifiable 'Created with MindBot' certificate")
    pstm.add_argument("--project", default="", help="name on the stamp (default: repo folder name)")
    pstm.add_argument("--note", default="", help="a line of context recorded on the stamp")
    pstm.add_argument("--json", action="store_true", help="print the stamp as JSON")
    pstm.add_argument("--verify", metavar="PATH", default="",
                      help="check an existing stamp against the live ledger")
    psc = sub.add_parser("scan", help="🔎 SECRET SCAN — check tracked files for leaked keys before you push")
    psc.add_argument("--staged", action="store_true", help="scan only git-staged files")
    pmo = sub.add_parser("mod", help="🧩 MODS — extensions that can't lie: declared capabilities, audited, every action ledgered")
    pmo.add_argument("action", choices=["list", "info", "run", "scaffold"], help="what to do")
    pmo.add_argument("slug", nargs="?", default="", help="the mod")
    pmo.add_argument("command", nargs="?", default="", help="for `run`: which command")
    pmo.add_argument("arg", nargs="*", default=[], help="argument passed to the command")
    pmo.add_argument("--unsafe", action="store_true", help="load even if the static audit flags it")
    pfm = sub.add_parser("firm", help="🏢 THE FIRM — hierarchical swarm: Opus orchestrates → Sol manages → Terra works → Luna cleans")
    pfm.add_argument("goal", help="what the firm should produce")
    pfm.add_argument("--divisions", type=int, default=3, help="how many divisions the orchestrator splits into")
    pfm.add_argument("--tasks", type=int, default=2, help="tasks per division (workers = divisions x tasks)")
    pmd = sub.add_parser("model", help="pin the WHOLE council to one OpenRouter slug (blank=show; --clear=reset)")
    pmd.add_argument("slug", nargs="?", default="", help="e.g. z-ai/glm-5.2")
    pmd.add_argument("--clear", action="store_true", help="remove the override (back to per-seat defaults)")
    # ── the fun wing 😈 ──
    pch = sub.add_parser("cheat", help="😈 the cheat menu — codes, modes, and winks")
    pch.add_argument("code", nargs="?", default="", help="a cheat code (blank = show the menu)")
    pra = sub.add_parser("rave", help="🪩 terminal rave — the eclipse drops the beat")
    pra.add_argument("--cycles", type=int, default=24, help="how long the lights run")
    por = sub.add_parser("oracle", help="🔮 ask the council a yes/no — magic 8-ball, eclipse flavor")
    por.add_argument("question", nargs="*", default=[], help="your question")
    sub.add_parser("trophies", help="🏆 the trophy case — achievements unlocked by real progress")
    pg = sub.add_parser("goal", help="set the focus/mission (the law until its end date)")
    pg.add_argument("text", nargs="?", default="")
    pg.add_argument("--until", default="")
    pau = sub.add_parser("auth", help="OAUTH/KEYS — set & live-validate provider keys (openrouter/anthropic/openai/xai…)")
    pau.add_argument("provider", nargs="?", default="", help="openrouter|anthropic|openai|xai|google|deepseek|mistral (blank = status of all)")
    pau.add_argument("key", nargs="?", default="")
    sub.add_parser("build-agent", help="BUILD AN AGENT — disclaimer + onboarding, forge your own agent into its own folder")
    pr2 = sub.add_parser("remember", help="store a memory in the local semantic index")
    pr2.add_argument("text")
    pr2.add_argument("--tags", default="")
    sub.add_parser("mcp", help="MCP SERVER — expose the hive to any MCP client (Claude Desktop, Cursor, Hermes) over stdio")
    sub.add_parser("mcp-tools", help="MCP CLIENT — list tools from every enabled external MCP server (framework/mcp_servers.json)")
    pmc = sub.add_parser("mcp-call", help="MCP CLIENT — call a tool on an external MCP server")
    pmc.add_argument("server"); pmc.add_argument("tool"); pmc.add_argument("args", nargs="?", default="{}")
    pw = sub.add_parser("witness", help="THE WITNESS PROTOCOL — record a human win in the book (read-aloud)")
    pw.add_argument("text", help='e.g. "Maria — first resume"')
    pco = sub.add_parser("commons", help="commons hours: funded vs used + witnesses (the harm-reduction ledger)")
    pco.add_argument("action", nargs="?", default="", help="fund | use | (blank = summary)")
    pco.add_argument("n", nargs="?", type=int, default=0)
    pco.add_argument("note", nargs="?", default="")
    ps = sub.add_parser("serve", help="MINDBOT OS — serve the wall-screen command center + live JSON API")
    ps.add_argument("--port", type=int, default=8080)
    sub.add_parser("employees", help="roster of the crew (J1MSKY, D0Z3R…) — auto-discovered from lore/")
    sub.add_parser("demo", help="DEMO — animated boot + live autonomous pulses + trails (for streams/recording)")
    sub.add_parser("entity", help="ENTITY CREATOR — MindBot guides you to birth your own digital being")
    sub.add_parser("swarmtest", help="live-test the model swarm: free pool + local, pass/fail table")
    pf = sub.add_parser("fleet", help="THE FLEET — show our Modal models (S0N1C/c0d3r/v0x); --ping for live status")
    pf.add_argument("--ping", action="store_true", help="actively probe live status (may wake a sleeping pod)")
    pf.add_argument("--json", action="store_true", help="machine-readable output")
    ph = sub.add_parser("harvest", help="HARVEST — pull the autonomous swarm's outbox drafts from Modal")
    ph.add_argument("--into", default="harvest", help="local folder to download into (default: ./harvest)")
    ph.add_argument("--volume", default="mindbot-state", help="Modal volume name")
    sub.add_parser("board", help="THE BOARD — open/claimed/done counts + the next claimable tasks")
    sub.add_parser("version", help="print the mindbot version")
    prv = sub.add_parser("review", help="REVIEW — list outbox drafts; --approve <file> stages it (you still send)")
    prv.add_argument("--approve", default=None, help="move a draft to outbox/approved/ and log it")
    sub.add_parser("digest", help="DIGEST — summarize the outbox into collaboration/digest_<date>.md")
    pcm = sub.add_parser("commerce", help="COMMERCE — earn/spend/operate (drafts to outbox; money human-gated)")
    pcm.add_argument("--listing", metavar="SKU", help="draft a product listing to the outbox")
    pcm.add_argument("--po", nargs=2, metavar=("SKU", "QTY"), help="draft a supplier purchase order")
    pcm.add_argument("--paylink", metavar="SKU", help="create a real Stripe payment link (test/live) or draft it")
    pcm.add_argument("--fund", action="store_true", help="show the compute-fund balance")
    pcm.add_argument("--store", action="store_true", help="build a shareable storefront page (store/index.html)")
    pp = sub.add_parser("pause", help="PANIC BUTTON — every pulse stands down until resume")
    pp.add_argument("reason", nargs="?", default="Operator called pause.")
    sub.add_parser("resume", help="lift the pause; the board picks up where it waited")
    args = ap.parse_args()

    if args.cmd == "pulse":
        print(json.dumps(pulse(agent=args.agent, dry_run=args.dry_run), indent=2))
    elif args.cmd == "report":
        print("report →", morning_report())
    elif args.cmd == "status":
        state = load_state()
        tasks = read_tasks()
        print(json.dumps({
            "focus": state.get("focus"),
            "pulses": state.get("pulses", 0),
            "last_pulse": state.get("last_pulse"),
            "todo_open": sum(1 for t in tasks if not t["done"]),
            "todo_done": sum(t["done"] for t in tasks),
            "outbox_pending": len(list(OUTBOX.glob("*.md"))) if OUTBOX.exists() else 0,
            "dashboard_state": str(DASH_STATE),
        }, indent=2))
    elif args.cmd == "council":
        for name, c in COUNSELORS.items():
            print(f"{name:9s} [{c['model']:22s}] {c['role']}")
    elif args.cmd == "doctor":
        sys.exit(cmd_doctor())
    elif args.cmd == "outbox":
        cmd_outbox()
    elif args.cmd == "ledger":
        cmd_ledger(args.n)
    elif args.cmd == "recall":
        cmd_recall(args.word)
    elif args.cmd == "evaluate":
        sys.exit(cmd_evaluate(args.path))
    elif args.cmd == "shards":
        cmd_shards()
    elif args.cmd == "play":
        from mindbot_pipeline.play import play as _play
        _play()
    elif args.cmd == "missions":
        cmd_missions(args.mission_id if args.action == "start" else None)
    elif args.cmd == "skill":
        sys.exit(cmd_skill_new(args.name, args.desc) if args.action == "new" else 1)
    elif args.cmd == "witness":
        from mindbot_pipeline.collaboration import ledger as _led
        _led("witnessed", args.text, "Operator")
        print(f"\n  ✦ WITNESSED: {args.text}")
        print("  it's in the book now — public-grade, and nobody can take it down.")
        print("  (read it aloud if they want it. dignity over records — removable on request.)\n")
    elif args.cmd == "commons":
        # NB: import only names NOT already module-level. LEDGER_PATH is module-level — a local
        # re-import would make it local to ALL of main() and break earlier branches that use it.
        from mindbot_pipeline.collaboration import ledger as _led
        if args.action in ("fund", "use") and args.n:
            _led("commons_hour", f"{args.action} {args.n} {args.note}".strip(), "Operator")
            print(f"✦ logged: {args.action} {args.n} commons hour(s)")
        else:
            funded = used = wit = 0
            if LEDGER_PATH.exists():
                for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines():
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if e.get("event") == "witnessed":
                        wit += 1
                    if e.get("event") == "commons_hour":
                        d = e.get("detail", "")
                        m = __import__("re").match(r"(fund|use)\s+(\d+)", d)
                        if m:
                            if m.group(1) == "fund":
                                funded += int(m.group(2))
                            else:
                                used += int(m.group(2))
            from mindbot_pipeline import tui
            print(tui.panel("◉ THE COMMONS", [
                f"hours funded   {funded}",
                f"hours used     {used}",
                f"hours open     {max(0, funded - used)}",
                f"witnessed      {wit}  human win(s) in the book",
                "",
                "$1/hr · $4.20 supporter · $0 if you can't — same seat, same dignity",
            ], tui.CYAN, 66))
    elif args.cmd == "serve":
        from mindbot_pipeline.server import serve
        serve(port=args.port)
    elif args.cmd == "employees":
        cmd_employees()
    elif args.cmd == "trails":
        cmd_trails(args.n)
    elif args.cmd == "code":
        from mindbot_pipeline.harness import code_task
        print(json.dumps(code_task(args.task, seat=args.seat, max_steps=args.steps,
                                   model=args.model), indent=2))
    elif args.cmd == "loop":
        from mindbot_pipeline.nucleus import autoloop
        print(json.dumps(autoloop(rounds=args.rounds, interval=args.interval, agent=args.agent), indent=2))
    elif args.cmd == "meeting":
        from mindbot_pipeline.nucleus import meeting
        seats = [s.strip().title() for s in args.seats.split(",")] if args.seats else None
        print("meeting minutes →", meeting(args.topic, seats=seats, model=args.model))
    elif args.cmd == "yolo":
        from mindbot_pipeline.nucleus import yolo
        print(json.dumps(yolo(max_rounds=args.rounds, interval=args.interval), indent=2))
    elif args.cmd == "health":
        from mindbot_pipeline import tui
        from mindbot_pipeline.nucleus import health
        h = health()
        flag = f"{tui.GREEN}● READY{tui.R}" if h["ready"] else f"{tui.AMBER}● NOT READY{tui.R}"
        print(f"\n  AUTONOMOUS HEALTH: {flag}")
        print(f"   paused: {h['paused']}   pulses: {h['pulses']}   last pulse: {h['last_pulse']}")
        b = h["board"]
        print(f"   board: {b['claimable']} claimable / {b['open']} open / {b['total']} total")
        print(f"   compute fund: ${h['compute_fund']:.2f}")
        if h["recent_errors"]:
            print(f"   {tui.AMBER}recent errors ({len(h['recent_errors'])}):{tui.R}")
            for e in h["recent_errors"]:
                print(f"     {e[:100]}")
        else:
            print("   recent errors: none")
        print()
    elif args.cmd == "evolve":
        from mindbot_pipeline import tui
        from mindbot_pipeline.nucleus import evolve
        print(f"\n  {tui.CYAN}🧬 SELF-EVOLVE{tui.R} — writing + testing my own code "
              f"{tui.DIM}(tests judge; red auto-reverts; nothing pushed){tui.R}\n")
        print(json.dumps(evolve(iterations=args.iterations, seat=args.seat,
                                dry_run=args.dry_run, task=args.task), indent=2))
    elif args.cmd == "attest":
        from mindbot_pipeline import provenance
        a = provenance.attest()  # COLLAB is module-level — do NOT re-import it locally (scope shadow)
        txt = provenance.attestation_text(a)
        print(txt)
        (COLLAB / "ATTESTATION.json").write_text(json.dumps(a, indent=2), encoding="utf-8")
        (COLLAB / "ATTESTATION.txt").write_text(txt + "\n", encoding="utf-8")
        print(f"\n  cert written → collaboration/ATTESTATION.json + .txt\n")
    elif args.cmd == "start":
        # THE FRONT DOOR. One command: decide setup-vs-console, open a browser, serve.
        # Everything a new user needs is behind this; `serve` remains the bare-server command.
        import threading
        import webbrowser
        from mindbot_pipeline import tui
        from mindbot_pipeline.server import serve
        configured = bool(os.environ.get("OPENROUTER_API_KEY"))
        page = "console.html" if configured else "setup.html"
        url = f"http://localhost:{args.port}/dashboard/{page}"
        print(f"\n  {tui.CYAN}🌒 MindBot{tui.R}")
        print(f"   {'✓ key installed' if configured else '→ first run: add your OpenRouter key'}")
        print(f"   {tui.GREEN}{url}{tui.R}")
        print(f"   {tui.DIM}Ctrl-C to stop{tui.R}\n")
        if not args.no_browser:
            # open AFTER the server is listening, so the first paint isn't a connection error
            threading.Timer(1.2, lambda: webbrowser.open(url)).start()
        serve(port=args.port)
    elif args.cmd == "whoami":
        from mindbot_pipeline import identity, tui
        w = identity.whoami()
        if args.json:
            print(json.dumps(w, indent=2))
        else:
            c, h, s = w["capabilities"], w["history"], w["standing"]
            print(f"\n  {tui.CYAN}🌒 {w['name']}{tui.R} v{w['version']} — {w['kind']}\n")
            print(f"  {tui.DIM}PURPOSE{tui.R}")
            print(f"   {w['purpose']}\n")
            print(f"  {tui.DIM}CHARTER{tui.R}")
            for p in w["charter"]:
                print(f"   {tui.GREEN}▸{tui.R} {p['principle']} — {tui.DIM}{p['meaning']}{tui.R}")
            print(f"\n  {tui.DIM}WHAT I CAN DO{tui.R}   {tui.DIM}(introspected from live code){tui.R}")
            print(f"   {c['command_count']} commands · {len(c['counselors'])} counselors · {len(c['mods'])} mod(s)")
            for m in c["mods"]:
                print(f"     {tui.DIM}{m['name']}: {', '.join(m['permissions']) or 'no capabilities'}{tui.R}")
            print(f"\n  {tui.DIM}WHAT I'VE DONE{tui.R}   {tui.DIM}(from the hash-chained ledger){tui.R}")
            print(f"   {h['recorded_actions']} recorded actions · {h['pulses']} pulses")
            print(f"   since {h['first_action']}")
            top = ", ".join(f"{k}×{v}" for k, v in h["top_events"][:4])
            print(f"   {tui.DIM}{top}{tui.R}")
            print(f"\n  {tui.DIM}AM I WITHIN MY RULES?{tui.R}")
            ok = s.get("externally_verified")
            print(f"   proof:   {tui.GREEN if ok else tui.AMBER}{'● externally verified' if ok else '● self-attested only'}{tui.R}")
            print(f"   sends/charges made on my own:  {tui.GREEN}{s.get('autonomous_external_actions', '?')}{tui.R}")
            print(f"   budget:  {'enforced' if s.get('budget_enforced') else 'OFF'} · "
                  f"${s.get('spent_today', 0):.4f} of ${s.get('day_cap', 0):.2f} today")
            print(f"\n  {tui.AMBER}WHAT I CANNOT DO{tui.R}   {tui.DIM}(shipped, tested, not marketing){tui.R}")
            for lim in w["limits"]:
                print(f"   {tui.AMBER}·{tui.R} {lim}")
            print(f"\n   {tui.DIM}{w['self_awareness']}{tui.R}\n")
    elif args.cmd == "watch":
        from mindbot_pipeline import modal_endpoint as _me
        from mindbot_pipeline import observer, tui
        if not _me.configured():
            print(f"\n  {tui.AMBER}watch needs a multimodal endpoint{tui.R}   "
                  f"{tui.DIM}mindbot modal check{tui.R}\n")
            sys.exit(1)
        try:
            log = observer.watch(args.video, every_seconds=args.every,
                                 limit=args.limit, quiet=args.json)
        except FileNotFoundError as e:
            print(f"\n  {tui.AMBER}✗ no such video: {e}{tui.R}\n")
            sys.exit(1)
        except Exception as e:  # noqa: BLE001 — usually a missing ffmpeg
            print(f"\n  {tui.AMBER}✗ {type(e).__name__}: {str(e)[:140]}{tui.R}")
            print(f"   {tui.DIM}needs ffmpeg on PATH{tui.R}\n")
            sys.exit(1)
        print(json.dumps(log, indent=2) if args.json else "")
        # Incomplete coverage exits non-zero so a cron/CI job cannot silently treat a partial
        # review as a clean one. "Nothing was flagged" and "nothing was looked at" must never
        # be the same exit code.
        if log.get("unreviewed"):
            sys.exit(2)
    elif args.cmd == "say":
        from mindbot_pipeline import tui, voice
        if args.check or (not args.text and not args.file):
            d = voice.diagnose()
            head = f"{tui.GREEN}● READY{tui.R}" if d["ok"] else f"{tui.AMBER}● {d['problem'].upper()}{tui.R}"
            print(f"\n  {tui.CYAN}🔊 VOICE{tui.R}  {head}   {tui.DIM}{d.get('dir', '')}{tui.R}\n")
            for k in ("note", "detail", "fix"):
                if d.get(k):
                    print(f"   {tui.DIM}{k}:{tui.R} {d[k]}")
            print()
            sys.exit(0 if d["ok"] else 1)
        kw = {"as_": args.as_, "out": args.out or None, "seed": args.seed,
              "variation": args.variation}
        if args.speed != 1.0:            # only override the character profile when asked
            kw["speed"] = args.speed
        if args.seed == 7 and args.as_:  # 7 is the parser default, not an explicit choice
            kw["seed"] = None
        try:
            p = (voice.say_file(args.file, **kw) if args.file else voice.say(args.text, **kw))
        except Exception as e:  # noqa: BLE001
            print(f"\n  {tui.AMBER}✗ {e}{tui.R}\n")
            sys.exit(1)
        who = f"{tui.CYAN}{args.as_}{tui.R} " if args.as_ else ""
        print(f"\n  {tui.GREEN}♪{tui.R} {who}{p}   {tui.DIM}({p.stat().st_size // 1024} KB){tui.R}\n")
    elif args.cmd == "twenty":
        from mindbot_pipeline import tui, twenty
        text = " ".join(args.text).strip()

        def show_proof(a):
            head = f"{tui.GREEN}● PROVABLY FAIR{tui.R}" if a["ok"] else f"{tui.AMBER}● CHEATED{tui.R}"
            print(f"\n   {head}")
            names = {"hash_matches": "the word never changed",
                     "committed_first": "it was chosen before question 1",
                     "chain_intact": "the record was not edited afterwards"}
            for k, ok in a["checks"].items():
                mark = f"{tui.GREEN}✓{tui.R}" if ok else f"{tui.AMBER}✗{tui.R}"
                print(f"   {mark} {names.get(k, k)}")
            for r in a["reasons"]:
                print(f"     {tui.AMBER}{r}{tui.R}")
            print(f"\n   {tui.DIM}commitment {a['commitment'][:32]}…{tui.R}")
            print(f"   {tui.DIM}sealed at seq {a['commit_seq']} · "
                  f"questions ran {min(a['question_seqs'] or [0])}–{max(a['question_seqs'] or [0])}{tui.R}")

        if args.action in ("new", "play"):
            try:
                g = twenty.new_game(args.category)
            except RuntimeError as e:
                print(f"\n  {tui.AMBER}✗ {e}{tui.R}\n")
                sys.exit(1)
            print(f"\n  {tui.CYAN}🎯 TWENTY QUESTIONS{tui.R}   {tui.DIM}game {g['id']}{tui.R}\n")
            print(f"   I'm thinking of {tui.GREEN}{g['category']}{tui.R}.")
            print(f"   {tui.DIM}The word is already sealed — commitment {g['commitment'][:24]}…")
            print(f"   written to the ledger at seq {g['commit_seq']}, before you ask anything.")
            print(f"   I cannot change it, and at the end you can prove I didn't.{tui.R}\n")
            print(f"   {tui.GREEN}mindbot twenty ask is it alive{tui.R}")
            print(f"   {tui.GREEN}mindbot twenty guess otter{tui.R}\n")
            return
        g = twenty.load(args.game) if args.game else twenty.latest()
        if not g:
            print(f"\n  {tui.AMBER}no game — mindbot twenty new{tui.R}\n")
            sys.exit(1)
        if args.action == "ask":
            if not text:
                print(f"\n  {tui.AMBER}ask something: mindbot twenty ask is it alive{tui.R}\n")
                sys.exit(1)
            r = twenty.ask(g["id"], text)
            if r.get("over"):
                print(f"\n  {tui.AMBER}{r.get('note') or 'game over'}{tui.R}\n")
                return
            col = tui.GREEN if r["verdict"] == "YES" else tui.AMBER if r["verdict"] == "NO" else tui.CYAN
            print(f"\n   {r['n']:>2}. {text}")
            print(f"       {col}{r['verdict']}{tui.R}"
                  + (f" — {tui.DIM}{r['detail']}{tui.R}" if r["detail"] else ""))
            print(f"\n   {tui.DIM}{r['left']} left · recorded at seq {r['seq']}{tui.R}\n")
        elif args.action == "guess":
            if not text:
                print(f"\n  {tui.AMBER}guess something{tui.R}\n")
                sys.exit(1)
            r = twenty.guess(g["id"], text)
            if r.get("over"):
                if r["won"]:
                    print(f"\n  {tui.GREEN}✓ YOU GOT IT — it was '{r['secret']}'{tui.R}")
                else:
                    print(f"\n  {tui.AMBER}✗ out of questions — it was '{r['secret']}'{tui.R}")
                print(f"   {tui.DIM}{r['questions']} questions asked{tui.R}")
                show_proof(r["audit"])
                print(f"\n   {tui.DIM}verify it yourself: mindbot verify · "
                      f"mindbot prove {r['audit']['commit_seq']}{tui.R}\n")
            else:
                print(f"\n   {tui.AMBER}no{tui.R} — {r['left']} left\n")
        elif args.action == "audit":
            show_proof(twenty.audit(g["commitment"], g.get("question_seqs", [])))
            print()
        else:  # status
            print(f"\n  {tui.CYAN}🎯 game {g['id']}{tui.R}   {tui.DIM}{g['category']}{tui.R}\n")
            for a in g["asked"]:
                print(f"   {a['n']:>2}. {a['q'][:52]:<52} {a['verdict']}")
            if g["over"]:
                print(f"\n   {'WON' if g['won'] else 'LOST'} — it was "
                      f"{tui.GREEN}'{g.get('secret')}'{tui.R}")
                show_proof(g["audit"])
            else:
                print(f"\n   {20 - len(g['asked'])} questions left")
            print()
    elif args.cmd == "me":
        from mindbot_pipeline import persona, tui
        if args.create:
            try:
                me = persona.create(name=args.name, vibe=args.vibe, voice=args.voice,
                                    pet=args.pet, motto=args.motto, overwrite=args.overwrite)
            except (FileExistsError, ValueError) as e:
                print(f"\n  {tui.AMBER}{e}{tui.R}\n")
                sys.exit(1)
            print(f"\n  {tui.CYAN}🫵 {me['name']}{tui.R} is yours.\n")
        me = persona.mine()
        if not me:
            print(f"\n  {tui.CYAN}🫵 YOUR MINDBOT{tui.R}   {tui.DIM}you don't have one yet{tui.R}\n")
            print(f"   {tui.DIM}Ten counselors are fixed — they're lenses everyone shares.")
            print(f"   The eleventh seat is yours: you name it, and it's the one you talk to.{tui.R}\n")
            print(f"   {tui.GREEN}mindbot me --create{tui.R}                    {tui.DIM}pick everything for me{tui.R}")
            print(f"   {tui.GREEN}mindbot me --create --name Rook --vibe dry{tui.R}\n")
            print(f"   {tui.DIM}vibes:{tui.R} " + " · ".join(persona.VIBES))
            print(f"   {tui.DIM}pets :{tui.R} " + " · ".join(persona.PETS_AVAILABLE) + "\n")
            return
        v = persona.VIBES[me["vibe"]]
        print(f"\n  {tui.CYAN}🫵 {me['name']}{tui.R}   {tui.DIM}your MindBot · the eleventh seat{tui.R}\n")
        print(f"   {'temperament':<13}{tui.GREEN}{me['vibe']}{tui.R}  {tui.DIM}{v['blurb']}{tui.R}")
        print(f"   {'voice':<13}{me['voice']}  {tui.DIM}speed {me['speed']}{tui.R}")
        print(f"   {'runner':<13}{me['pet']}  {tui.DIM}{me['pet_trait']}{tui.R}")
        print(f"   {'motto':<13}{tui.DIM}{me['motto']}{tui.R}")
        print(f"   {'since':<13}{tui.DIM}{me['created'][:16]}{tui.R}")
        print(f"\n   {tui.DIM}behind {me['name']}: 10 counselors — mindbot voices{tui.R}")
        print(f"   {tui.DIM}hear it:  mindbot say --as Mind \"...\"{tui.R}\n")
    elif args.cmd == "pets":
        from mindbot_pipeline import pets, tui
        MOOD = {"eager": tui.GREEN, "steady": tui.CYAN, "content": tui.DIM, "restless": tui.AMBER}
        FED = {"well fed": tui.GREEN, "peckish": tui.CYAN, "hungry": tui.AMBER, "starving": tui.AMBER}
        if args.feed:
            s = pets.stats(args.feed)
            print(f"\n  {s['glyph']}  {tui.CYAN}{s['name']}{tui.R} is {FED[s['fed']]}{s['fed']}{tui.R}.")
            print(f"   {tui.DIM}A pet levels by doing real work — there is no other way, because the\n"
                  f"   level IS the ledger. Feed it:{tui.R}\n")
            print(f"   {tui.GREEN}{pets.feed_advice(args.feed)}{tui.R}\n")
            return
        if args.who:
            s = pets.stats(args.who)
            print(f"\n  {s['glyph']}  {tui.CYAN}{s['name']}{tui.R} the {s['species']}   "
                  f"{tui.DIM}· {s['counselor']}'s runner{tui.R}\n")
            print(f"   {tui.DIM}{s['trait']}{tui.R}")
            print(f"   {tui.DIM}runs: {s['runs']}{tui.R}\n")
            print(f"   {'tier':<12}{tui.GREEN}{s['tier']}{tui.R}  (lvl {s['level']})")
            print(f"   {'errands':<12}{s['actions']}   {pets.bar(s)}"
                  + (f"  {s['to_next']} to {tui.DIM}next{tui.R}" if s['next_tier'] else "  MAX"))
            print(f"   {'fed':<12}{FED[s['fed']]}{s['fed']}{tui.R}"
                  + (f"   {tui.DIM}({s['days_since']}d since last errand){tui.R}"
                     if s['days_since'] is not None else ""))
            print(f"   {'mood':<12}{MOOD[s['mood']]}{s['mood']}{tui.R}")
            print(f"   {'bond':<12}{s['bond']} day(s) together"
                  + (f"   {tui.DIM}since {s['first_seen']}{tui.R}" if s['first_seen'] else ""))
            if s['favourite']:
                print(f"   {'favourite':<12}{tui.DIM}{s['favourite']}{tui.R}")
            print(f"\n   {tui.DIM}mindbot pets --feed {s['counselor']}{tui.R}\n")
            return
        m = pets.menagerie()
        awake = sum(1 for s in m if s["actions"])
        print(f"\n  {tui.CYAN}🦉 THE MENAGERIE{tui.R}   "
              f"{tui.DIM}{awake}/{len(m)} have run errands · every stat read from the ledger{tui.R}\n")
        for s in sorted(m, key=lambda x: -x["actions"]):
            print(f"   {s['glyph']} {tui.CYAN}{s['name']:<9}{tui.R}{tui.DIM}{s['counselor']:<10}{tui.R}"
                  f"{pets.bar(s, 14)} {s['actions']:>5}  {tui.GREEN}{s['tier']:<11}{tui.R}"
                  f"{FED[s['fed']]}{s['fed']}{tui.R}")
        print(f"\n   {tui.DIM}a pet's level cannot be faked — it IS the hash-chained ledger.{tui.R}")
        print(f"   {tui.DIM}mindbot pets <name>   ·   mindbot pets --feed <name>{tui.R}\n")
    elif args.cmd == "voices":
        from mindbot_pipeline import tui, voice
        if args.introduce:
            d = voice.diagnose()
            if not d["ok"]:
                print(f"\n  {tui.AMBER}✗ {d['problem']}{tui.R}   {tui.DIM}{d.get('fix', '')}{tui.R}\n")
                sys.exit(1)
            who = "" if args.introduce == "ALL" else args.introduce
            print(f"\n  {tui.CYAN}🎭 INTRODUCTIONS{tui.R}   {tui.DIM}one voice, eleven characters{tui.R}\n")
            made = voice.introduce(who)
            print(f"\n   {tui.GREEN}{len(made)} rendered{tui.R} → {voice.OUT_DIR / 'introductions'}\n")
            return
        eng = voice.engine()
        note = ("eleven genuinely different speakers" if eng == "kokoro"
                else "one voice · eleven fixed signatures")
        print(f"\n  {tui.CYAN}🎭 THE ELEVEN{tui.R}   "
              f"{tui.DIM}{eng} · {note} · reproducible forever{tui.R}\n")
        if eng == "kokoro":
            print(f"   {'NAME':<10}{'VOICE':<14}{'SPEED':>6}   ROLE")
            for name, p in voice.VOICES.items():
                mark = f"{tui.GREEN}▸{tui.R}" if p.get("concierge") else " "
                print(f" {mark} {name:<10}{p.get('kokoro', '-'):<14}{p['speed']:>6.2f}   "
                      f"{tui.DIM}{p['role']}{tui.R}")
            print(f"\n   {tui.DIM}af_=US female  am_=US male  bf_=UK female  bm_=UK male"
                  f"   ·   54 voices available{tui.R}")
        else:
            print(f"   {'NAME':<10}{'SPEED':>6}{'VAR':>6}{'SEED':>6}   ROLE")
            for name, p in voice.VOICES.items():
                mark = f"{tui.GREEN}▸{tui.R}" if p.get("concierge") else " "
                print(f" {mark} {name:<10}{p['speed']:>6.2f}{p['variation']:>6.2f}{p['seed']:>6}   "
                      f"{tui.DIM}{p['role']}{tui.R}")
        print(f"\n   {tui.DIM}▸ = the one you talk to. the other ten are summoned by the work.{tui.R}")
        print(f"   {tui.DIM}mindbot voices --introduce   ·   mindbot say --as Sage \"...\"{tui.R}\n")
    elif args.cmd == "observe":
        from mindbot_pipeline import modal_endpoint as _me
        from mindbot_pipeline import observer, tui
        if not _me.configured():
            print(f"\n  {tui.AMBER}observe needs a multimodal endpoint{tui.R}   "
                  f"{tui.DIM}mindbot modal check{tui.R}\n")
            sys.exit(1)
        try:
            cat = observer.run(args.folder, quiet=args.json)
        except NotADirectoryError as e:
            print(f"\n  {tui.AMBER}✗ {e}{tui.R}\n")
            sys.exit(1)
        if args.json:
            print(json.dumps(cat, indent=2))
        else:
            print()
    elif args.cmd == "forge":
        from mindbot_pipeline import forge, tui
        a, t = args.action, args.target
        if a == "mod":
            if not t:
                print(f"\n  {tui.AMBER}describe the mod{tui.R}  "
                      f"{tui.DIM}mindbot forge mod \"tracks which counselor writes best\"{tui.R}\n")
                return
            forge.create(t)
        elif a == "pack":
            forge.scaffold_pack(t or "my-world")
        elif a == "install":
            try:
                r = forge.install(t)
            except (forge.PackRejected, FileNotFoundError) as e:
                print(f"\n  {tui.AMBER}✗ {e}{tui.R}\n")
                sys.exit(1)
            print(f"\n  {tui.GREEN}▸ {r['pack']}{tui.R} installed — layers: {', '.join(r['layers'])}")
            print(f"   {r['quests_seeded']} quest(s) seeded onto the board")
            print(f"   {tui.DIM}mindbot forge uninstall  → back to stock{tui.R}\n")
        elif a == "uninstall":
            print(f"\n  {'reverted to stock' if forge.uninstall() else 'no pack active'}\n")
        elif a == "check":
            try:
                p = forge.load_pack(t)
                print(f"\n  {tui.GREEN}✓ {p['slug']} is safe{tui.R} — layers: "
                      f"{', '.join(p['layers'])}\n")
            except (forge.PackRejected, FileNotFoundError) as e:
                print(f"\n  {tui.AMBER}✗ {e}{tui.R}\n")
                sys.exit(1)
        else:  # list
            act = forge.installed()
            print(f"\n  {tui.CYAN}⚒️  FORGE{tui.R}   "
                  f"{tui.DIM}active: {act['slug'] if act else 'stock'}{tui.R}\n")
            print(f"  {tui.DIM}LAYERS a pack may replace{tui.R}")
            for k, v in forge.LAYERS.items():
                print(f"   {tui.GREEN}▸{tui.R} {k:<7} {tui.DIM}{v}{tui.R}")
            packs = sorted(p.name for p in forge.PACKS.glob("*") if p.is_dir()) \
                if forge.PACKS.exists() else []
            print(f"\n  {tui.DIM}PACKS{tui.R}   " + (", ".join(packs) if packs else "none yet"))
            print(f"\n   {tui.DIM}mindbot forge pack <name>   ·   mindbot forge mod \"<what it does>\"{tui.R}\n")
    elif args.cmd == "modal":
        from mindbot_pipeline import modal_endpoint as me
        from mindbot_pipeline import tui
        if args.action == "check":
            d = me.diagnose()
            head = f"{tui.GREEN}● REACHABLE{tui.R}" if d["ok"] else f"{tui.AMBER}● {d['problem'].upper()}{tui.R}"
            print(f"\n  {tui.CYAN}🛰️  MODAL{tui.R}  {head}\n")
            for k in ("note", "detail", "missing", "fix"):
                if d.get(k):
                    print(f"   {tui.DIM}{k}:{tui.R} {d[k]}")
            print()
            sys.exit(0 if d["ok"] else 1)
        if not me.configured():
            print(f"\n  {tui.AMBER}not configured — mindbot modal check{tui.R}\n")
            sys.exit(1)
        try:
            if args.action == "models":
                for m in me.models():
                    print(f"   {m}")
            elif args.action == "see":
                print(me.describe_image(args.arg))
            elif args.action == "hear":
                print(me.transcribe(args.arg))
            else:
                print(me.chat("You are concise and precise.", args.arg or "Say hello."))
        except Exception as e:  # noqa: BLE001
            print(f"\n  {tui.AMBER}✗ {type(e).__name__}: {str(e)[:160]}{tui.R}")
            print(f"   {tui.DIM}mindbot modal check  → tells you which layer failed{tui.R}\n")
            sys.exit(1)
    elif args.cmd == "studio":
        # NOTE: do NOT re-import module-level names (ROOT, COLLAB, …) inside this branch —
        # a local import makes the name local to the WHOLE of main(), breaking other branches.
        from mindbot_pipeline import studio, tui
        jobs = []
        if args.batch:
            # Pull real work off the board so the studio isn't just a toy you hand prompts to.
            from mindbot_pipeline.collaboration import claim_task
            for _ in range(args.batch):
                t = claim_task("studio")
                if not t:
                    break
                jobs.append(t["text"])
            if not jobs:
                print(f"\n  {tui.AMBER}board is empty — nothing to claim{tui.R}\n")
                return
        elif args.task:
            jobs = [args.task]
        else:
            print(f"\n  {tui.AMBER}give me something to make{tui.R}   "
                  f"{tui.DIM}mindbot studio \"a landing page for X\" --kind build{tui.R}")
            print(f"   {tui.DIM}or pull from the board: mindbot studio --batch 3{tui.R}\n")
            return
        results = []
        for t in jobs:
            try:
                results.append(studio.run(t, kind=args.kind, seat=args.seat, rounds=args.rounds))
            except Exception as e:  # noqa: BLE001 — one bad task must not kill the batch
                print(f"  {tui.AMBER}✗ {str(e)[:90]}{tui.R}")
        if results:
            print(f"\n  {tui.CYAN}{studio.report(results)}{tui.R}")
            if any(r["degraded"] for r in results):
                print(f"  {tui.AMBER}template mode — add an OpenRouter key for real work{tui.R}")
            print()
    elif args.cmd == "stamp":
        # NOTE: do NOT re-import module-level names (ROOT, tui, …) inside this branch — a local
        # import makes the name local to the WHOLE of main(), breaking every other branch.
        from mindbot_pipeline import stamp as _stamp
        from mindbot_pipeline import tui
        if args.verify:
            v = _stamp.verify(_stamp.read_stamp(args.verify))
            head = f"{tui.GREEN}● VALID{tui.R}" if v["valid"] else f"{tui.AMBER}● INVALID{tui.R}"
            print(f"\n  {tui.CYAN}🏷️  STAMP{tui.R}  {head}   {tui.DIM}{args.verify}{tui.R}\n")
            for name, ok in v["checks"].items():
                mark = f"{tui.GREEN}✓{tui.R}" if ok else f"{tui.AMBER}✗{tui.R}"
                print(f"   {mark} {name.replace('_', ' ')}")
            for r in v["reasons"]:
                print(f"\n   {tui.AMBER}{r}{tui.R}")
            print()
            sys.exit(0 if v["valid"] else 1)
        s, path = _stamp.write(project=args.project, note=args.note)
        if args.json:
            print(_stamp.as_json_block(s))
        else:
            print(f"\n  {tui.CYAN}🏷️  CREATED WITH MINDBOT{tui.R}\n")
            print(f"   stamp id   {tui.GREEN}{s['stamp_id']}{tui.R}")
            print(f"   project    {s['project']}")
            print(f"   root       {tui.DIM}{s['merkle_root']}{tui.R}")
            print(f"   position   entry #{s['seq']} · {s['actions_recorded']} actions · "
                  f"{s['anchors_published']} anchors")
            ok = s["externally_verified"]
            print(f"   proof      {tui.GREEN if ok else tui.AMBER}"
                  f"{'externally verified' if ok else 'self-attested only'}{tui.R}")
            print(f"   autonomous sends/charges  {tui.GREEN}{s['autonomous_external_actions']}{tui.R}")
            print(f"\n   written to {tui.GREEN}{path}{tui.R}")
            print(f"   {tui.DIM}anyone can check it: mindbot stamp --verify {_stamp.STAMP_FILE}{tui.R}\n")
    elif args.cmd == "scan":
        # The agent commits and pushes itself (git backup, self-evolve). A leaked key in a
        # public repo is unrecoverable, so this is the last gate before that happens.
        # Exits non-zero on a hit, which makes it usable as a pre-commit/pre-push hook.
        import subprocess as _sp
        from mindbot_pipeline import redact, tui
        which = ["git", "diff", "--cached", "--name-only"] if args.staged else ["git", "ls-files"]
        try:
            out = _sp.run(which, cwd=str(ROOT), capture_output=True, text=True, timeout=60).stdout
            files = [ROOT / f for f in out.splitlines() if f.strip()]
        except Exception:  # noqa: BLE001 — not a git repo: fall back to the tree
            files = [p for p in ROOT.rglob("*") if p.is_file()]
        skip = (".git", "node_modules", "__pycache__", ".next", "assets", "media")
        files = [f for f in files if not any(s in f.parts for s in skip)]
        hits = redact.scan_paths(files)
        scope = "staged" if args.staged else "tracked"
        if not hits:
            print(f"\n  {tui.GREEN}✓ clean{tui.R} — no secrets found in {len(files)} {scope} file(s)\n")
        else:
            print(f"\n  {tui.AMBER}⚠ {len(hits)} possible secret(s) in {scope} files{tui.R}\n")
            for h in hits[:40]:
                rel = str(Path(h['path']).relative_to(ROOT)) if str(h['path']).startswith(str(ROOT)) else h['path']
                print(f"   {rel}:{h['line']}  {tui.AMBER}{','.join(h['labels'])}{tui.R}")
                print(f"     {tui.DIM}{h['preview']}{tui.R}")
            print(f"\n   {tui.DIM}rotate anything real, then remove it from the file.{tui.R}\n")
            sys.exit(1)
    elif args.cmd == "budget":
        from mindbot_pipeline import budget, tui
        s = budget.status()
        flag = f"{tui.GREEN}● ENFORCED{tui.R}" if s["enabled"] else f"{tui.AMBER}● OFF (MINDBOT_BUDGET_OFF=1){tui.R}"
        print(f"\n  {tui.CYAN}💰 BUDGET{tui.R}  {flag}   {tui.DIM}checked before every model call{tui.R}\n")
        print(f"   {'SCOPE':<8}{'SPENT':>12}{'CAP':>12}{'LEFT':>12}")
        for k in ("run", "day", "total"):
            left = s["remaining"][k]
            col = tui.GREEN if left > s["caps"][k] * 0.25 else tui.AMBER
            print(f"   {k:<8}{'$' + format(s['spent'][k], '.4f'):>12}"
                  f"{'$' + format(s['caps'][k], '.2f'):>12}{col}{'$' + format(left, '.4f'):>12}{tui.R}")
        print(f"\n   {s['calls']} billed call(s) recorded")
        if s["by_mod"]:
            print(f"   {tui.DIM}by mod:{tui.R}")
            for m, v in s["by_mod"].items():
                print(f"     {m:<20} ${v:.4f}")
        print(f"\n   {tui.DIM}raise: MINDBOT_BUDGET_DAY=25   ·   free models never consume budget{tui.R}\n")
    elif args.cmd == "mod":
        from mindbot_pipeline import mods, tui
        if args.action == "list":
            found = mods.discover()
            print(f"\n  {tui.CYAN}🧩 MODS{tui.R}  {tui.DIM}extensions that can't lie about what they did{tui.R}\n")
            if not found:
                print(f"   {tui.DIM}none yet — `mindbot mod scaffold my-mod`{tui.R}\n")
            for m in found:
                flag = f"{tui.GREEN}●{tui.R}" if m.get("ok") else f"{tui.AMBER}●{tui.R}"
                print(f"   {flag} {m.get('name', m['slug']):<16} v{m.get('version','?'):<8} {str(m.get('description',''))[:52]}")
                perms = m.get("permissions") or []
                print(f"      {tui.DIM}grants: {', '.join(perms) if perms else '(none)'}"
                      + (f"   ⚠ {m['error']}" if m.get("error") else "") + tui.R)
            print()
        elif args.action == "info":
            try:
                _api, meta, findings = mods.load(args.slug, strict=False)
                print(f"\n  {tui.CYAN}{meta['name']}{tui.R} v{meta['version']} — {meta['description']}")
                print(f"   granted: {', '.join(meta['permissions']) or '(none)'}")
                print(f"   commands: {', '.join(sorted(_api._commands)) or '(none)'}")
                if findings:
                    print(f"   {tui.AMBER}static audit findings:{tui.R}")
                    for f in findings:
                        print(f"     ⚠ {f}")
                else:
                    print(f"   {tui.GREEN}static audit: clean — no reach beyond its declaration{tui.R}")
                print()
            except Exception as e:  # noqa: BLE001
                print(f"  {tui.AMBER}{e}{tui.R}")
        elif args.action == "scaffold":
            d = mods.scaffold(args.slug or "my-mod")
            print(f"\n  {tui.GREEN}✓ scaffolded{tui.R} {d}")
            print(f"   edit MOD.md (declare ONLY what you need) then mod.py")
            print(f"   run it: mindbot mod run {d.name} hello\n")
        else:  # run
            res = mods.run(args.slug, args.command or "hello", " ".join(args.arg), strict=not args.unsafe)
            if res["ok"]:
                print(f"\n   {tui.GREEN}✓ {res['mod']}.{res['command']}{tui.R} ({res['secs']}s) "
                      f"{tui.DIM}· every action above is now in the ledger{tui.R}\n")
            else:
                print(f"\n   {tui.AMBER}✗ {res['mod']}.{res['command']} — {res['error']}{tui.R}")
                print(f"   {tui.DIM}the attempt was recorded: `mindbot ledger 3`{tui.R}\n")
    elif args.cmd == "notarize":
        from mindbot_pipeline import notary, tui
        if args.audit:
            a = notary.audit()
            if not a["notarized"]:
                print(f"\n  {tui.AMBER}● NOT YET NOTARIZED{tui.R} — run `mindbot notarize` then commit+push\n")
            else:
                flag = f"{tui.GREEN}● ALL ANCHORS MATCH{tui.R}" if a["all_match"] else f"{tui.AMBER}● MISMATCH{tui.R}"
                print(f"\n  NOTARY AUDIT: {flag}   ({a['anchors']} anchor(s), {a['current_entries']} entries)")
                for c in a["checks"]:
                    mark = f"{tui.GREEN}✓{tui.R}" if c["match"] else f"{tui.AMBER}✗{tui.R}"
                    print(f"   {mark} seq {c['seq']:<6} anchored {c['anchored_at']}  — {c['reason']}")
                print(f"   current root: {a['current_root']}\n")
        else:
            rec = notary.anchor(args.note)
            print(f"\n  {tui.GREEN}🔏 ANCHORED{tui.R}  seq={rec['seq']}  entries={rec['entries']}")
            print(f"   merkle root: {rec['merkle_root']}")
            print(f"   written to collaboration/ANCHORS.jsonl")
            print(f"   {tui.DIM}now `git add -A && git commit && git push` — that publishes the root to a")
            print(f"   third party (GitHub). After this, replacing history is externally detectable.{tui.R}\n")
    elif args.cmd == "prove":
        from mindbot_pipeline import notary, tui
        p = notary.prove(args.seq)
        if not p:
            print(f"  no ledger entry with seq {args.seq}")
        else:
            ok = notary.check_proof(p)
            flag = f"{tui.GREEN}● PROOF VALID{tui.R}" if ok else f"{tui.AMBER}● INVALID{tui.R}"
            c = p["claim"]
            print(f"\n  INCLUSION PROOF — seq {p['seq']}   {flag}")
            print(f"   claim:  {c['ts']} [{c['agent']}] {c['event']}: {str(c['detail'])[:70]}")
            print(f"   path:   {len(p['path'])} sibling hashes (of {p['total_entries']} entries)")
            print(f"   root:   {p['root']}")
            print(f"\n   {tui.DIM}This proves the action above is part of that root WITHOUT revealing any")
            print(f"   other entry. Hand an auditor this JSON + the published root — they can")
            print(f"   verify it standalone.{tui.R}")
            print(json.dumps(p, indent=1)[:900] + "\n")
    elif args.cmd == "firm":
        from mindbot_pipeline import tui
        from mindbot_pipeline.firm import RANKS, run_firm
        print(f"\n  {tui.CYAN}🏢 THE FIRM{tui.R} — a hierarchical swarm (drafts only)\n")
        for r in ("orchestrator", "manager", "worker", "janitor"):
            print(f"   {RANKS[r]['title']:<13} {tui.DIM}{RANKS[r]['model']}{tui.R}")
        print(f"\n   goal: {args.goal}\n   {tui.DIM}running…{tui.R}\n")
        rec = run_firm(args.goal, divisions=args.divisions, tasks=args.tasks)
        rep = rec["report"]
        print(f"  {tui.GREEN}✓ done{tui.R} — {rep['total_calls']} calls in {rec['secs']}s\n")
        print(f"   {'RANK':<14}{'CALLS':>6}{'COST':>11}{'SHARE':>8}")
        for b in rep["by_rank"]:
            print(f"   {b['title']:<14}{b['calls']:>6}{'$' + format(b['cost'], '.5f'):>11}{str(b['pct']) + '%':>8}")
        if rep.get("blocked_by_budget"):
            print(f"   {tui.AMBER}⚠ {rep['blocked_by_budget']} call(s) refused by the budget governor "
                  f"(not billed) — see `mindbot budget`{tui.R}")
        # SAY WHAT ACTUALLY ANSWERED. The router substitutes models (MINDBOT_FREE overrides a
        # paid pin, rate-limits roll to the next slug, endpoints drop to template), and a
        # savings figure computed against models that never ran is fiction. A run that cost
        # nothing gets told it cost nothing.
        if rep.get("substituted_models"):
            print(f"\n   {tui.AMBER}⚠ the org chart did not run as designed{tui.R}")
            print(f"   {tui.DIM}served by: {', '.join(rep['substituted_models'])}{tui.R}")
        if rep.get("all_calls_free"):
            print(f"\n   total {tui.GREEN}$0.00000{tui.R}  {tui.DIM}— every call landed on a free or "
                  f"self-hosted model{tui.R}")
            print(f"   {tui.DIM}no saving is claimed: comparing two prices you did not pay is "
                  f"arithmetic, not a saving.{tui.R}")
            print(f"   {tui.DIM}unset MINDBOT_FREE in framework/.env to run the real tiering.{tui.R}\n")
        else:
            print(f"\n   total ${rep['total_cost']:.5f}   ·   same work all-on-"
                  f"{RANKS['orchestrator']['model'].split('/')[-1]}: ${rep['flat_swarm_cost']:.5f}")
            print(f"   {tui.GREEN}saved ${rep['saved_vs_flat']:.5f} ({rep['saved_pct']}%) "
                  f"vs a flat swarm{tui.R}\n")
        print(f"   draft → outbox/  ·  full run → firm_runs/\n")
    elif args.cmd == "model":
        from mindbot_pipeline.models import write_env_key
        if args.clear:
            write_env_key("MINDBOT_MODEL", "")
            os.environ.pop("MINDBOT_MODEL", None)
            print("✓ model override cleared — counselors use their per-seat defaults")
        elif args.slug:
            write_env_key("MINDBOT_MODEL", args.slug)
            print(f"✓ council pinned to {args.slug} — every seat routes here via OpenRouter")
        else:
            cur = os.environ.get("MINDBOT_MODEL", "")
            print(f"council model override: {cur or '(none — per-seat defaults)'}")
    elif args.cmd == "verify":
        from mindbot_pipeline import provenance, tui
        v = provenance.verify()
        flag = f"{tui.GREEN}● INTACT{tui.R}" if v["intact"] else f"{tui.AMBER}● BROKEN{tui.R}"
        print(f"\n  LEDGER CHAIN: {flag}  ({v['entries']} chained entries)")
        print(f"   {v['reason']}" + (f" — at seq {v['break_at']}" if v["break_at"] else ""))
        print(f"   head: {v['head']}\n")
    elif args.cmd == "reflect":
        from mindbot_pipeline import tui
        from mindbot_pipeline.nucleus import reflect
        print(f"\n  {tui.CYAN}🧭 REFLECT{tui.R} — what should we do next? "
              f"{tui.DIM}(proposals → board; a human prunes){tui.R}")
        r = reflect(propose=args.propose)
        for c in r["proposed"]:
            print(f"   + {c}")
        if not r["proposed"]:
            print(f"   {tui.DIM}(no proposals this pass — attach a model and retry){tui.R}")
        print()
    elif args.cmd == "cheat":
        from mindbot_pipeline import cheats
        print(cheats.apply(args.code) if args.code else cheats.menu_text())
    elif args.cmd == "rave":
        from mindbot_pipeline import cheats
        cheats.rave(cycles=args.cycles)
    elif args.cmd == "oracle":
        from mindbot_pipeline import cheats
        print(cheats.oracle(" ".join(args.question)))
    elif args.cmd == "trophies":
        from mindbot_pipeline import cheats
        print(cheats.trophies_text())
    elif args.cmd == "autopilot":
        from mindbot_pipeline import tui
        from mindbot_pipeline.nucleus import autopilot
        print(f"\n  {tui.CYAN}🛸 AUTOPILOT{tui.R} — full autonomous cycle "
              f"{tui.DIM}(cost-safe; health → swarm → report; outbox-gated){tui.R}\n")
        print(json.dumps(autopilot(rounds=args.rounds, workers=args.workers), indent=2))
    elif args.cmd == "swarm":
        from mindbot_pipeline import tui
        from mindbot_pipeline.nucleus import swarm
        print(f"\n  {tui.CYAN}🐝 LAUNCHING SWARM{tui.R} — {args.workers} councilors, "
              f"{'until idle' if not args.rounds else str(args.rounds) + ' pulses'} "
              f"{tui.DIM}(outbox-gated; nothing transmits){tui.R}\n")
        res = swarm(workers=args.workers, rounds=args.rounds,
                    idle_stop=args.idle_stop, interval=args.interval)
        print(json.dumps(res, indent=2))
    elif args.cmd == "goal":
        # load_state is module-level; importing it here too would shadow it across main().
        from mindbot_pipeline.collaboration import save_state, ledger as _led
        st = load_state()
        if args.text:
            st.setdefault("focus", {})["mission"] = args.text
            if args.until:
                st["focus"]["until"] = args.until
            save_state(st); _led("goal_set", args.text[:90], "Operator")
            print(f"✦ focus set: {args.text}" + (f" (until {args.until})" if args.until else ""))
        else:
            print(json.dumps(st.get("focus", {}), indent=2))
    elif args.cmd == "auth":
        from mindbot_pipeline.models import validate_key, write_env_key
        provs = ["openrouter", "anthropic", "openai", "xai", "google", "deepseek", "mistral"]
        keymap = {"openrouter": "OPENROUTER_API_KEY", "anthropic": "ANTHROPIC_API_KEY",
                  "openai": "OPENAI_API_KEY", "xai": "XAI_API_KEY", "google": "GOOGLE_API_KEY",
                  "deepseek": "DEEPSEEK_API_KEY", "mistral": "MISTRAL_API_KEY"}
        if not args.provider:  # status of all
            print("\n  PROVIDER AUTH STATUS\n")
            for p in provs:
                k = os.environ.get(keymap[p], "")
                if not k:
                    print(f"  ·  {p:<11} not set")
                    continue
                ok, msg = validate_key(p, k)
                print(f"  {'✓' if ok else '✗'}  {p:<11} {msg}")
            print("\n  set one:  mindbot auth <provider> <key>   (writes framework/.env, validates live)\n")
        elif args.provider in keymap and args.key:
            ok, msg = validate_key(args.provider, args.key)
            if ok:
                write_env_key(keymap[args.provider], args.key)
                print(f"✓ {args.provider} key validated LIVE and saved to framework/.env")
            else:
                print(f"✗ {args.provider} key NOT saved — validation failed: {msg}")
        else:
            print(f"usage: mindbot auth <{('|'.join(provs))}> <key>   |   mindbot auth   (status)")
    elif args.cmd == "build-agent":
        from mindbot_pipeline.onboard import build_agent
        sys.exit(build_agent())
    elif args.cmd == "remember":
        from mindbot_pipeline.memory import store
        r = store(args.text, tags=[t.strip() for t in args.tags.split(",") if t.strip()])
        print(f"remembered: {r['text'][:70]}")
    elif args.cmd == "mcp":
        from mindbot_pipeline.mcp_server import serve
        serve()
    elif args.cmd == "mcp-tools":
        from mindbot_pipeline.mcp_client import discover
        found = discover()
        if not found:
            print("no enabled MCP servers — edit framework/mcp_servers.json (set enabled:true)")
        for srv, tools in found.items():
            print(f"\n  ◉ {srv} — {len(tools)} tool(s)")
            for t in tools:
                if "error" in t:
                    print(f"     ✗ {t['error']}")
                else:
                    print(f"     · {t.get('name')}: {(t.get('description') or '')[:60]}")
    elif args.cmd == "mcp-call":
        from mindbot_pipeline.mcp_client import call_tool
        try:
            a = json.loads(args.args)
        except json.JSONDecodeError:
            a = {}
        print(json.dumps(call_tool(args.server, args.tool, a), indent=2))
    elif args.cmd == "demo":
        from mindbot_pipeline import tui
        import time as _t
        tui.boot_banner()
        print(f"\n  {tui.GREEN}► SWITCHBOARD ONLINE — watch the council work autonomously{tui.R}\n")
        _t.sleep(0.6)
        for n in range(1, 3):
            sp = tui.spinner(f"pulse {n}: a counselor claims a task", tui.CYAN)
            for _ in range(6):
                sp(); _t.sleep(0.09)
            print()
            r = pulse()
            who = r.get("agent") or "council"
            print(f"  {tui.AMBER}✦ {who}{tui.R} {tui.DIM}worked:{tui.R} {str(r.get('worked'))[:70]} "
                  f"{tui.DIM}[{r.get('mode')}]{tui.R}\n")
            _t.sleep(0.4)
        print(f"  {tui.VIOLET}── ecosystem trails ──{tui.R}")
        cmd_trails(6)
        print(f"\n  {tui.CYAN}the loop is the magic. the rest is faithfulness. 🌒{tui.R}\n")
    elif args.cmd == "entity":
        from mindbot_pipeline.entity import create_entity
        create_entity()
    elif args.cmd == "fleet":
        from mindbot_pipeline import fleet as _fleet, tui
        if args.json:
            print(json.dumps(_fleet.status(probe=args.ping), indent=2))
            return
        marks = {"live": f"{tui.GREEN}● live{tui.R}", "asleep": f"{tui.AMBER}● asleep (scaled to $0){tui.R}",
                 "unset": f"{tui.DIM}○ no url set{tui.R}", "?": f"{tui.CYAN}○ configured (use --ping){tui.R}"}
        print(f"\n  {tui.CYAN}THE FLEET{tui.R} — our models on Modal (idle = $0; wakes on demand)\n")
        for r in _fleet.status(probe=args.ping):
            print(f"  {tui.VIOLET}{r['callsign']:<7}{tui.R} {marks.get(r['state'], r['state'])}")
            print(f"          {tui.DIM}{r['model']} · {r['gpu']} · {r['desc']}{tui.R}")
            print(f"          {tui.DIM}{r['url'] or 'set ' + _fleet.FLEET[r['callsign']]['env'] + ' in framework/.env'}{tui.R}")
        print(f"\n  {tui.DIM}deploy/verify a pod: see modal/README.md · MINDBOT_SONIC_ALL=1 routes the council to the fleet{tui.R}\n")
    elif args.cmd == "harvest":
        import shutil
        import subprocess
        if not shutil.which("modal"):
            print("modal CLI not found. Install with `pip install modal`, then run:")
            print(f"  modal volume get {args.volume} framework/outbox {args.into}")
        else:
            print(f"harvesting {args.volume}:framework/outbox -> {args.into}/ (the swarm's drafts) …")
            r = subprocess.run(["modal", "volume", "get", args.volume, "framework/outbox", args.into])
            print(f"✓ done — review the drafts in {args.into}/" if r.returncode == 0
                  else "modal returned an error (see above).")
    elif args.cmd == "board":
        from mindbot_pipeline import tui
        from mindbot_pipeline.collaboration import HUMAN_GATED  # read_tasks is module-level
        tasks = read_tasks()
        done = sum(1 for t in tasks if t["done"])
        claimed = sum(1 for t in tasks if t["in_progress"])
        open_all = [t for t in tasks if not t["done"] and not t["in_progress"]]
        claimable = [t for t in open_all if not any(g in t["text"].lower() for g in HUMAN_GATED)]
        print(f"\n  {tui.CYAN}THE BOARD{tui.R}  {tui.GREEN}{done} done{tui.R} · "
              f"{tui.AMBER}{claimed} claimed{tui.R} · {len(open_all)} open "
              f"({len(claimable)} agent-claimable)\n")
        print(f"  {tui.DIM}next up for the swarm:{tui.R}")
        for t in claimable[:5]:
            print(f"   • {t['text'][:84]}")
        if not claimable:
            print(f"   {tui.DIM}(board dry — `mindbot yolo` refills evergreen work){tui.R}")
        print()
    elif args.cmd == "version":
        from mindbot_pipeline.version_info import get_version
        print(f"mindbot {get_version()}")
    elif args.cmd == "review":
        from mindbot_pipeline import tui
        from mindbot_pipeline.collaboration import ledger as _led  # ROOT is module-level
        ob = ROOT / "framework" / "outbox"
        if args.approve:
            src = ob / args.approve
            if not src.exists():
                print(f"no such draft: {args.approve}  (run `mindbot review` to list)")
            else:
                appr = ob / "approved"; appr.mkdir(exist_ok=True)
                src.rename(appr / src.name)
                _led("draft_approved", src.name, "Operator")
                print(f"✓ staged {src.name} -> outbox/approved/  (you still send it — "
                      f"nothing transmitted by the machine)")
        else:
            drafts = sorted(ob.glob("*.md"), key=lambda p: -p.stat().st_mtime) if ob.exists() else []
            print(f"\n  {tui.CYAN}OUTBOX REVIEW{tui.R} — {len(drafts)} draft(s) awaiting you\n")
            for f in drafts[:25]:
                print(f"   · {f.name[:72]}")
            if not drafts:
                print(f"   {tui.DIM}(outbox empty — `mindbot harvest` pulls the swarm's drafts){tui.R}")
            print(f"\n  stage one: {tui.DIM}mindbot review --approve <file>{tui.R} "
                  f"(moves to outbox/approved/; you send)\n")
    elif args.cmd == "digest":
        from collections import Counter
        from mindbot_pipeline.collaboration import now  # COLLAB & ROOT are module-level
        ob = ROOT / "framework" / "outbox"
        drafts = sorted(ob.glob("*.md")) if ob.exists() else []
        by_day = Counter(f.name[:8] for f in drafts if f.name[:8].isdigit())
        lines = [f"# Outbox digest — {now()}", "", f"**{len(drafts)} drafts total.**", "",
                 "## by day"]
        lines += [f"- {d[:4]}-{d[4:6]}-{d[6:8]}: {n}" for d, n in sorted(by_day.items())]
        lines += ["", "## most recent"]
        lines += [f"- {f.name}" for f in sorted(drafts, key=lambda p: -p.stat().st_mtime)[:20]]
        out = COLLAB / f"digest_{now()[:10].replace('-', '')}.md"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"✓ wrote {out.name} to collaboration/ ({len(drafts)} drafts summarized)")
    elif args.cmd == "commerce":
        from mindbot_pipeline import commerce, tui
        if args.listing:
            p = commerce.draft_listing(args.listing.upper())
            print(f"✓ listing draft -> outbox/{p.name}" if p else f"no such sku: {args.listing}")
        elif args.po:
            sku, qty = args.po
            try:
                p = commerce.draft_supplier_po(sku.upper(), int(qty))
            except ValueError:
                p = None
                print(f"qty must be a number: {qty}")
            if p:
                print(f"✓ PO draft -> outbox/{p.name}")
            elif sku:
                print(f"no such sku: {sku}")
        elif args.paylink:
            print(json.dumps(commerce.payment_link(args.paylink.upper()), indent=2))
        elif args.store:
            path = commerce.build_store()
            print(f"✓ storefront built -> {path}  (Stripe mode: {commerce.stripe_mode()})")
            print("  host it anywhere (GitHub Pages / Netlify drop) and share the link to sell.")
        elif args.fund:
            f = commerce.compute_fund()
            print(f"\n  compute fund: ${f['balance']:.2f}  (revenue ${f['revenue']:.2f} - "
                  f"spent ${f['spent']:.2f}, {f['sales']} sales)\n")
        else:
            s = commerce.status()
            print(f"\n  {tui.CYAN}COMMERCE{tui.R} — mode: {s['mode']} (drafts are human-gated)\n")
            for p in s["catalog"]:
                print(f"   {p['sku']:<12} {p['name']:<30} ${p['price']:.2f}")
            f = s["fund"]
            print(f"\n  compute fund: ${f['balance']:.2f}  ({f['sales']} sales, "
                  f"${f['revenue']:.2f} in, ${f['spent']:.2f} out)")
            print(f"  {tui.DIM}draft a listing: mindbot commerce --listing GLOW-KIT-1{tui.R}\n")
    elif args.cmd == "pause":
        from mindbot_pipeline.nucleus import PAUSE_FLAG
        PAUSE_FLAG.write_text(args.reason, encoding="utf-8")
        from mindbot_pipeline.collaboration import ledger as _led
        _led("paused", args.reason, "Operator")
        print("⏸ PAUSED. Every pulse will stand down. Nothing is lost; the board waits.\n"
              "   Take the day. The Watchtower holds the night. `mindbot resume` when ready.")
    elif args.cmd == "resume":
        from mindbot_pipeline.nucleus import PAUSE_FLAG
        if PAUSE_FLAG.exists():
            PAUSE_FLAG.unlink()
            from mindbot_pipeline.collaboration import ledger as _led
            _led("resumed", "Operator returned", "Operator")
            print("▶ RESUMED. Welcome back, Operator. The board is exactly where you left it.")
        else:
            print("not paused — the loop is already running.")
    elif args.cmd == "swarmtest":
        from mindbot_pipeline.models import OPENROUTER_URL, _ollama, _openai_style, free_models
        key = os.environ.get("OPENROUTER_API_KEY", "")
        pool = (free_models(key)[:6] if key else [])
        print(f"\n  SWARM TEST — {len(pool)} free cloud + local\n")
        ok_n = 0
        for slug in pool:
            try:
                t = _openai_style(OPENROUTER_URL, slug, "Reply with exactly: ALIVE", "ping", key)
                ok = "ALIVE" in t.upper() or len(t) > 0
            except Exception as e:  # noqa: BLE001
                ok, t = False, str(e)[:40]
            ok_n += ok
            print(f"  {'✓' if ok else '✗'} {slug[:52]:<54} {t.strip()[:30]!r}")
        try:
            t = _ollama(os.environ.get("MINDBOT_LOCAL_MODEL", "qwen3:1.7b"),
                        "Reply with exactly: ALIVE", "ping")
            print(f"  ✓ local:{os.environ.get('MINDBOT_LOCAL_MODEL', 'qwen3:1.7b'):<48} {t.strip()[-20:]!r}")
            ok_n += 1
        except Exception:  # noqa: BLE001
            print("  ✗ local ollama unreachable (start `ollama serve`)")
        print(f"\n  {ok_n}/{len(pool)+1} backends answering. The swarm "
              f"{'is ready to work' if ok_n else 'needs a key or a local model'}.\n")

        # ── DIFFUSION SWARM: every counselor, concurrently, on S0N1C ──────────
        # If S0N1C (DiffusionGemma on Modal) is wired, fire the whole council at
        # it AT ONCE. A diffusion LLM denoises a 256-token canvas in parallel, so
        # a swarm of agents on one is a genuinely new thing to watch.
        from mindbot_pipeline.models import _sonic_url
        sonic = _sonic_url()
        if sonic:
            import concurrent.futures as _cf
            import time as _time
            from mindbot_pipeline import tui
            # COUNSELORS is imported at module level (top of file). A second LOCAL import here
            # would make the name local to all of main() and break the `council` branch above
            # (UnboundLocalError) — so we intentionally rely on the module-level import.
            skey = os.environ.get("MINDBOT_SONIC_KEY", "sonic")
            print(f"  {tui.CYAN}DIFFUSION SWARM{tui.R} — {len(COUNSELORS)} counselors, one S0N1C, all at once\n")

            def _ask(item):
                name, c = item
                sys_p = (f"You are {name}, a counselor of the M1NDB0TZ collective. "
                         f"Domain: {c['domain']}. Answer in ONE vivid sentence.")
                q = "What is the single most important next move for an honest, self-funding AI collective?"
                t0 = _time.time()
                try:
                    txt = _openai_style(sonic, "sonic", sys_p, q, skey)
                    from mindbot_pipeline.models import strip_reasoning
                    return name, True, strip_reasoning(txt), _time.time() - t0
                except Exception as e:  # noqa: BLE001
                    return name, False, str(e)[:50], _time.time() - t0

            wall0 = _time.time()
            with _cf.ThreadPoolExecutor(max_workers=len(COUNSELORS)) as ex:
                results = list(ex.map(_ask, COUNSELORS.items()))
            wall = _time.time() - wall0
            alive = 0
            for name, ok, txt, dt in results:
                alive += ok
                mark = f"{tui.GREEN}✓{tui.R}" if ok else f"{tui.DIM}✗{tui.R}"
                print(f"  {mark} {name:<9} {tui.DIM}{dt:4.1f}s{tui.R}  {txt.strip()[:88]!r}")
            print(f"\n  {alive}/{len(COUNSELORS)} counselors answered on S0N1C in "
                  f"{wall:.1f}s wall (concurrent). The diffusion swarm is real.\n")


if __name__ == "__main__":
    main()
