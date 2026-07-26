"""The nucleus: wake → read state → do ONE unit of work → verify → outbox → ledger → die.

Direct descendant of MINDBOT_HQ/architect/architect.py, extended with the
counselor stack and the pipeline stages. A pulse is one heartbeat of the swarm.

Constitution invariant every function here upholds: work goes to OUTBOX as a DRAFT
and stops there — nothing is ever transmitted. `verify()` is the gate; the loops
(pulse/autoloop/yolo/swarm/autopilot) only ever produce drafts + ledger lines.

Extend:
  - new run mode / daemon shape -> add a top-level fn (mirror swarm/autoloop) and
    wire it into the CLI in cli.py (subparser + elif in main()).
  - new evergreen refill work -> append a one-line task to EVERGREEN.
  - new safe self-improvement task -> append to SELF_TASKS (must be additive +
    test-gated; the harness auto-reverts a red change).
  - new draft-gate rule -> add a check inside verify() (return False to block).
  - counselors/stages/providers live in their own modules; extend those there.
"""

import datetime
import json
import os
from pathlib import Path

from . import stages
from .collaboration import (COLLAB, PIPE_DIR, ROOT, claim_task, complete_task,
                            ledger, load_state, now, save_state, update_dashboard,
                            write_handoff)
from .counselors import COUNSELORS, persona_prompt, route
from .logs import get_logger
from .models import llm, strip_reasoning

OUTBOX = PIPE_DIR / "outbox"
_log = get_logger("nucleus")


def verify(text: str) -> tuple[bool, str]:
    """Loud gate before anything reaches the outbox."""
    if not text or not text.strip():
        return False, "empty draft"
    lowered = text.lower()
    # Block drafts that CLAIM a transmission already happened — the loop only ever
    # drafts, so such a phrase is either a hallucination or a constitution breach.
    for banned in ("i have sent", "posted to", "payment complete", "emailed "):
        if banned in lowered:
            return False, f"draft claims to have transmitted ({banned!r}) — constitution violation"
    return True, "passes" + (" (carries NEED markers)" if "[NEED:" in text else "")


def outbox_write(agent: str, task_text: str, draft: str, mode: str = "") -> Path:
    OUTBOX.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in task_text[:50])
    path = OUTBOX / f"{stamp}_{agent}_{safe}.md"
    banner = ""
    if mode == "local" or (mode.startswith("openrouter") and os.environ.get("MINDBOT_FREE")):
        # Field-tested lesson (2026-06-11): small local models fabricate completed
        # work in confident prose. The outbox contains it; this banner names it.
        banner = ("> ⚠ LOCAL-MODEL DRAFT — small models routinely claim work that never "
                  "happened. Verify EVERY factual claim against the ledger before using "
                  "one word of this. Status claims without ledger lines are fiction.\n\n")
    path.write_text(f"# Draft by {agent} — {now()} [mode: {mode or 'stage'}]\n"
                    f"{banner}## Task\n{task_text}\n\n## Draft\n{draft}\n",
                    encoding="utf-8")
    return path


PAUSE_FLAG = PIPE_DIR / "PAUSED"


def pulse(agent: str | None = None, dry_run: bool = False) -> dict:
    """One heartbeat. Claims one task, routes it, works it, hands off. Never raises."""
    if PAUSE_FLAG.exists():
        # The Operator pulled the cord. Everything stops, nothing is lost, no shame.
        update_dashboard(pulse_status="⏸ PAUSED by Operator — the board waits, the ledger holds")
        return {"agent": agent, "worked": None, "mode": "paused", "ok": True,
                "note": PAUSE_FLAG.read_text(encoding="utf-8").strip() or "paused"}
    state = load_state()
    focus = state.get("focus", {}).get("mission", "")
    result = {"agent": agent, "worked": None, "mode": None, "ok": False}

    task = claim_task(agent or "pulse")
    if not task:
        # No open tasks: the pulse still does real work — refresh the tracker, note it.
        update_dashboard(pulse_status="idle — no unclaimed tasks", focus=focus)
        ledger("pulse_idle", "no unclaimed tasks; dashboard refreshed", agent or "pulse")
        result.update(worked="(idle: dashboard refresh)", ok=True, mode="local")
        return result

    # An explicit agent overrides the router; otherwise route() picks the seat by task text.
    counselor, reason = route(task["text"]) if not agent else (agent, "explicit")
    spec = COUNSELORS.get(counselor, COUNSELORS["Sage"])  # Sage is the fallback seat
    # A matching stage handler short-circuits the model: mechanical, local, no billing.
    handler = stages.match_handler(task["text"])

    if handler and not dry_run:
        # Mechanical stage work runs locally — no model needed, fully real.
        draft, detail = handler(task["text"], state)
        mode = "stage"
    elif dry_run:
        draft, detail, mode = f"[dry-run] would work: {task['text']}", "dry-run", "dry"
    else:
        sysp = persona_prompt(counselor)
        prompt = (f"Focus (law until its end date): {focus}\nTask claimed from BIG_TODO_LIST: "
                  f"{task['text']}\nWorkspace root: {ROOT}\nProduce the complete draft now.")
        draft, mode = llm(spec["provider"], spec["model"], sysp, prompt)
        if mode != "template":  # strip leaked <start_working_out>/<SOLUTION> tags from real drafts
            draft = strip_reasoning(draft)
        detail = f"llm:{mode}"

    ok, why = verify(draft)
    if ok and mode == "template":
        # No model was reachable: close the claim but re-queue a fresh copy so the
        # task isn't lost AND isn't falsely 'done'. The ledger stays honest.
        from .collaboration import add_task
        complete_task(counselor, task["text"][:60], note="no model backend — re-queued")
        if "[requeued]" not in task["text"]:
            add_task(f"[requeued] {task['text']}", counselor)
        write_handoff(counselor, f"pulse (no model): {task['text'][:80]}",
                      ["no model backend reachable; task re-queued for a counselor with a brain attached"],
                      blockers=["model backend unavailable this wake"],
                      next_steps=["set API keys or start Ollama, then re-pulse"])
    elif ok:
        path = outbox_write(counselor, task["text"], draft, mode=mode)
        complete_task(counselor, task["text"][:60],
                      note=f"draft → outbox/{path.name} [{detail}]")
        write_handoff(counselor, f"pulse: {task['text'][:80]}",
                      [f"draft written to outbox/{path.name} ({why}, mode={mode})"],
                      next_steps=["human: review outbox draft; approve or annotate"])
    else:
        ledger("verify_failed", f"{task['text']} — {why}", counselor)
        write_handoff(counselor, f"pulse FAILED verify: {task['text'][:80]}",
                      [f"verification refused the draft: {why}"],
                      blockers=[why],
                      next_steps=["re-attempt with the failure reason attached"])

    state["pulses"] = state.get("pulses", 0) + 1
    state["last_pulse"] = now()
    save_state(state)
    update_dashboard(pulse_status=f"{counselor}: {task['text'][:70]} [{mode}]",
                     focus=focus, pulses=state["pulses"],
                     last_counselor=counselor, route_reason=reason)
    result.update(agent=counselor, worked=task["text"], ok=ok, mode=mode)
    (_log.info if ok else _log.warning)("pulse %s: %r [mode=%s ok=%s]",
                                        counselor, str(task["text"])[:70], mode, ok)
    return result


def autoloop(rounds: int = 0, interval: float = 0.0, agent: str | None = None,
             idle_stop: int = 3) -> dict:
    """THE AUTONOMOUS DAEMON - pulse, again and again, until idle or paused or done.

    rounds=0 means run until the board goes idle (idle_stop empty pulses in a row)
    or the PAUSE flag appears. This is the 'it runs itself' command. Honest: it only
    does what a single pulse does - claim ONE task, draft, hand off - just on repeat.
    """
    import time as _t
    done_pulses, idle_streak, worked = 0, 0, []
    ledger("autoloop_start", f"rounds={rounds or 'until-idle'} agent={agent or 'auto'}", "autoloop")
    while True:
        if (PIPE_DIR / "PAUSED").exists():
            ledger("autoloop_paused", "PAUSE flag - standing down", "autoloop")
            break
        r = pulse(agent=agent)
        done_pulses += 1
        w = r.get("worked")
        if w and "idle" not in str(w):
            worked.append(f"{r.get('agent')}: {str(w)[:60]}")
            idle_streak = 0
        else:
            idle_streak += 1
        if rounds and done_pulses >= rounds:
            break
        if not rounds and idle_streak >= idle_stop:
            ledger("autoloop_idle", f"board idle after {done_pulses} pulses", "autoloop")
            break
        if interval > 0:
            _t.sleep(interval)
    ledger("autoloop_done", f"{done_pulses} pulses, {len(worked)} produced work", "autoloop")
    return {"pulses": done_pulses, "worked": worked}


EVERGREEN = [  # refill work so YOLO/swarm never runs dry — mechanical + revenue, free, real
    "Mine the latest handoffs for gaps and standing blockers",
    "Groom TODO health and refresh the tracker",
    "Run intake scan of the workspace and refresh the manifest",
    "Dream a skill from the council's noticed gaps",
    "Compile dataset stats / corpus status for the tracker",
    "Watchtower: focus guard sweep - release stuck claims, flag drift",
    # revenue-oriented refills — the loop advances the money goal on its own (drafts only)
    "Draft a short Compute-Fund support post for X/Discord (drafts only; a human posts)",
    "Draft a product listing for a digital SKU (the Guide or the Hermes Skill Pack)",
    "Draft a 3-tweet thread on the self-funding-agent idea for the Hermes hackathon",
    "Draft 3 short-video hooks for the storefront (glow kit / compute fund)",
]


def yolo(max_rounds: int = 40, interval: float = 0.0) -> dict:
    """YOLO MODE - it never stops. Pulses forever; when the board goes idle it
    REFILLS itself with evergreen work so the hive keeps producing. Still 100%
    constitutional: every draft stops at the outbox, nothing transmits. The safe
    kind of reckless. Stops on PAUSE flag or max_rounds (a runaway backstop).
    """
    import time as _t
    from .collaboration import add_task, read_tasks
    done, produced, refills = 0, [], 0
    ledger("yolo_start", f"max_rounds={max_rounds}", "yolo")
    while done < max_rounds:
        if (PIPE_DIR / "PAUSED").exists():
            ledger("yolo_paused", "PAUSE - standing down", "yolo")
            break
        # Human-gated tasks (human/operator/[need:/gpu) are NOT claimable by the loop —
        # they wait for a person. Only autonomous work counts toward "is the board dry?".
        claimable = [t for t in read_tasks() if not t["done"] and not t["in_progress"]
                     and not any(g in t["text"].lower() for g in
                                 ("human", "operator", "[need:", "gpu"))]
        if not claimable:  # board dry -> refill (the never-stop trick)
            seed = EVERGREEN[refills % len(EVERGREEN)]
            add_task(f"[YOLO] {seed}", "yolo")
            refills += 1
        r = pulse()
        done += 1
        w = r.get("worked")
        if w and "idle" not in str(w):
            produced.append(f"{r.get('agent')}: {str(w)[:55]}")
        if interval > 0:
            _t.sleep(interval)
    ledger("yolo_done", f"{done} rounds, {len(produced)} produced, {refills} refills", "yolo")
    return {"rounds": done, "produced": produced, "refills": refills}


def swarm(workers: int = 3, rounds: int = 0, agent: str | None = None,
          idle_stop: int = 3, interval: float = 0.0) -> dict:
    """LAUNCH SWARM — N councilors pulse CONCURRENTLY against the shared board.

    A real parallel swarm, not a sequential loop: each worker thread claims its OWN task
    (claims are atomic via the collaboration lock) while the slow model work runs in parallel.
    Wall-clock collapses from sum-of-tasks to longest-task — many drafts at once. Still 100%
    constitutional: every draft stops at the outbox, nothing transmits.

    rounds=0  → run until the board goes idle (idle_stop empty pulses across the swarm) or PAUSE.
    rounds=N  → stop after N total pulses across all workers.
    """
    import threading
    import time as _t
    lock = threading.Lock()          # guards the shared counters below (board writes use the
    stop = threading.Event()         # collaboration lock inside pulse())
    counts = {"pulses": 0, "idle": 0}
    produced: list[str] = []
    workers = max(1, int(workers))
    ledger("swarm_launch", f"{workers} workers, rounds={rounds or 'until-idle'}", "swarm")

    def worker(wid: int) -> None:
        while not stop.is_set():
            if (PIPE_DIR / "PAUSED").exists():
                stop.set()
                break
            try:
                r = pulse(agent=agent)
            except Exception as e:  # noqa: BLE001 — one bad pulse must not kill the worker
                _log.exception("swarm worker %d: pulse crashed: %s", wid, e)
                r = {"agent": f"w{wid}", "worked": None}
            with lock:
                counts["pulses"] += 1
                w = r.get("worked")
                if w and "idle" not in str(w):
                    produced.append(f"w{wid} {r.get('agent')}: {str(w)[:50]}")
                    counts["idle"] = 0
                else:
                    counts["idle"] += 1
                if rounds and counts["pulses"] >= rounds:
                    stop.set()
                elif not rounds and counts["idle"] >= idle_stop:
                    stop.set()
            if interval > 0 and not stop.is_set():
                _t.sleep(interval)

    threads = [threading.Thread(target=worker, args=(i + 1,), daemon=True)
               for i in range(workers)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    ledger("swarm_done", f"{counts['pulses']} pulses, {len(produced)} produced work", "swarm")
    return {"workers": workers, "pulses": counts["pulses"], "produced": produced}


def meeting(topic: str, seats: list | None = None, model: str | None = None) -> str:
    """A COUNCIL MEETING - 3 seats deliberate in turn, then Sage synthesizes.

    Real multi-perspective deliberation, not one model. Minutes -> outbox (drafts only).
    """
    seats = seats or ["Sage", "Forge", "Vanguard"]
    transcript, minutes = [], [f"# COUNCIL MEETING - {topic}", f"*{now()} - seats: {', '.join(seats)}*", ""]
    for s in seats:
        c = COUNSELORS.get(s, COUNSELORS["Sage"])
        sysp = (persona_prompt(s) + " You are in a COUNCIL MEETING. Give your position in "
                "3-4 sentences, in voice. Build on or push against what others said. "
                "No headers. End with a concrete recommendation.")
        prior = "\n".join(transcript[-4:])
        text, _md = llm(c["provider"], model or c["model"], sysp,
                        (f"Discussion so far:\n{prior}\n\n" if prior else "") + f"Topic: {topic}\nYour turn, {s}:")
        text = strip_reasoning(text)[:700]
        transcript.append(f"{s}: {text}")
        # show the ACTUAL brain: a MINDBOT_MODEL override rides in the mode ("openrouter:<slug>"),
        # so the minutes credit the model that truly answered, not just the seat's default lean.
        shown = _md.split(":", 1)[1] if _md.startswith("openrouter:") else c["model"]
        minutes += [f"## {s}  ({shown})", text, ""]
    sysp = (persona_prompt("Sage") + " Synthesize this council meeting into a DECISION: "
            "2-3 sentences, then 'ACTIONS:' with 1-3 concrete next steps (drafts only - "
            "humans send). Name an owner seat per action.")
    syn, _ = llm(COUNSELORS["Sage"]["provider"], model or COUNSELORS["Sage"]["model"], sysp,
                 "Meeting transcript:\n" + "\n".join(transcript) + "\n\nSynthesis:")
    syn = strip_reasoning(syn)[:800]
    minutes += ["## SYNTHESIS - Sage", syn, "", "*drafted in council; a human Operator approves any external action.*"]
    OUTBOX.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = OUTBOX / f"{stamp}_MEETING_{topic[:30].replace(' ', '_')}.md"
    path.write_text("\n".join(minutes), encoding="utf-8")
    ledger("meeting", f"{topic[:60]} - {len(seats)} seats -> {path.name}", "council")
    return str(path)


def morning_report() -> str:
    """The 07:00 full report: ledger digest, outbox inventory, TODO state, next moves."""
    from .collaboration import LEDGER_PATH, read_tasks
    today = datetime.date.today().isoformat()
    events = []
    if LEDGER_PATH.exists():
        for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                # `or True` deliberately keeps every event — the date check is a vestige;
                # the real trim is the [-200:] tail below (digest, not just-today).
                if e["ts"].startswith(today) or True:  # full tail; trimmed below
                    events.append(e)
            except json.JSONDecodeError:
                continue
    events = events[-200:]
    tasks = read_tasks()
    drafts = sorted(OUTBOX.glob("*.md")) if OUTBOX.exists() else []
    done = [t for t in tasks if t["done"]]
    open_t = [t for t in tasks if not t["done"]]
    lines = [
        f"# MORNING REPORT — {now()}",
        "",
        f"**Pulses since genesis:** {load_state().get('pulses', 0)}",
        f"**TODO:** {len(done)} done / {len(open_t)} open / {len(tasks)} total",
        f"**Outbox awaiting human approval:** {len(drafts)} drafts",
        "",
        "## Drafts to review (agent proposes, operator disposes)",
        *[f"- outbox/{p.name}" for p in drafts[-25:]],
        "",
        "## Last ledger events",
        *[f"- {e['ts']} [{e['agent']}] {e['event']}: {e['detail'][:100]}" for e in events[-30:]],
        "",
        "## Open tasks (top 15)",
        *[f"- {t['text'][:110]}" for t in open_t[:15]],
        "",
        "*The loop is the magic. See you tonight. — the council*",
    ]
    report = "\n".join(lines) + "\n"
    out = COLLAB / f"MORNING_REPORT_{today}.md"
    out.write_text(report, encoding="utf-8")
    update_dashboard(last_report=str(out.name))
    ledger("morning_report", out.name, "Sage")
    return str(out)


def health() -> dict:
    """Is the autonomous system READY to run unattended? One glanceable self-check.

    ready == not paused AND there is claimable (non-human-gated) work AND no recent errors in
    the operational log. Used by `mindbot health` and as a pre-flight before launching a swarm.
    """
    from .collaboration import read_tasks
    from .logs import recent_errors
    from . import commerce
    st = load_state()
    tasks = read_tasks()
    open_t = [t for t in tasks if not t["done"] and not t["in_progress"]]
    claimable = [t for t in open_t if not any(
        g in t["text"].lower() for g in ("human", "operator", "[need:", "gpu"))]
    paused = (PIPE_DIR / "PAUSED").exists()
    errs = recent_errors(5)
    hard = [e for e in errs if " ERROR " in e]   # ERRORs block; WARNINGs only inform
    try:
        balance = commerce.compute_fund()["balance"]
    except Exception:  # noqa: BLE001
        balance = 0.0
    return {
        "ready": (not paused) and bool(claimable) and not hard,
        "paused": paused,
        "pulses": st.get("pulses", 0),
        "last_pulse": st.get("last_pulse"),
        "board": {"open": len(open_t), "claimable": len(claimable), "total": len(tasks)},
        "compute_fund": balance,
        "recent_errors": errs,
    }


# Safe, ADDITIVE self-improvement tasks — they add (tests/docs), they don't rewrite core
# logic, and the test gate + auto-revert make even a bad attempt harmless. The model that
# writes a passing new test has genuinely improved the repo; one that breaks it gets reverted.
SELF_TASKS = [
    "Add a stdlib unittest in framework/tests/ for an untested function in "
    "mindbot_pipeline/fleet.py (e.g. that status() returns a list). No network. "
    "Run `python -m unittest discover tests` before done.",
    "Add a stdlib unittest in framework/tests/ for mindbot_pipeline/version_info.py "
    "(get_version returns a non-empty string). Run the suite before calling done.",
    "Improve ONE thin module docstring in mindbot_pipeline/ (edit only the docstring, "
    "change no code). Run `python -m unittest discover tests` before done.",
    "Add a stdlib unittest asserting every counselor in mindbot_pipeline/counselors.py "
    "COUNSELORS has a 'voice' or 'domain' field. Run the suite before done.",
]


def evolve(iterations: int = 1, seat: str = "Forge", dry_run: bool = False,
           task: str | None = None) -> dict:
    """SELF-IMPROVEMENT — the system writes, TESTS, and proposes its OWN code.

    Each iteration runs the coding harness (jailed to the repo; tests are the judge; red →
    auto-revert) on a safe additive task, then drafts a proposal to the outbox for a human to
    commit. THE differentiator: it doesn't draft text for you to implement — it implements +
    verifies, then asks you to merge. Cost-safe; never pushes; never touches main.

    dry_run=True reverts any kept change after proving the loop (leaves the tree clean).
    """
    os.environ.setdefault("MINDBOT_NO_SONIC", "1")   # cost-safe self-improvement
    from . import harness
    results = []
    _log.info("evolve: starting (%d iteration(s), seat=%s, dry_run=%s)", iterations, seat, dry_run)
    for i in range(max(1, iterations)):
        if (PIPE_DIR / "PAUSED").exists():
            break
        t = task or SELF_TASKS[i % len(SELF_TASKS)]
        res = harness.code_task(t, seat=seat, max_steps=10)
        if res.get("ok") and res.get("touched"):
            note = (f"Task: {t}\n\nFiles changed: {res['touched']}\n"
                    f"Tests: GREEN (the harness ran the full suite).\n"
                    f"Harness summary: {res.get('summary', '')}\n\n"
                    f"Review: `git diff` — commit it if good. A human merges; the machine only proposes.")
            outbox_write(seat, f"self-evolve: {t[:48]}", note, mode="harness")
            ledger("self_evolve_proposed", f"{res['touched']} GREEN", "evolve")
            _log.info("evolve: proposed %s (GREEN)", res["touched"])
            if dry_run:
                harness._revert(res["touched"])
        else:
            ledger("self_evolve_nochange", f"{t[:50]} — {res.get('summary', '')[:60]}", "evolve")
            _log.info("evolve: no change kept (%s)", res.get("summary", "")[:60])
        results.append({"task": t[:70], "ok": bool(res.get("ok")), "touched": res.get("touched", [])})
    return {"iterations": len(results), "dry_run": dry_run, "results": results}


def reflect(propose: int = 3) -> dict:
    """SELF-DIRECTION — the council reviews what it has done and proposes its OWN next goals.

    Reads the recent ledger + the board + the focus mission, asks Sage for the highest-leverage
    next moves, and PROPOSES them to the board as [REFLECT] tasks (a human prunes; the swarm can
    then claim them). The system decides WHAT to do next, not just how. Cost-safe; proposals only.
    """
    import re as _re
    os.environ.setdefault("MINDBOT_NO_SONIC", "1")
    from .collaboration import LEDGER_PATH, add_task, read_tasks
    focus = load_state().get("focus", {}).get("mission", "")
    recent = []
    if LEDGER_PATH.exists():
        for ln in LEDGER_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()[-40:]:
            try:
                e = json.loads(ln)
                recent.append(f"{e['event']}: {e['detail'][:60]}")
            except Exception:  # noqa: BLE001
                pass
    open_n = sum(1 for t in read_tasks() if not t["done"] and not t["in_progress"])
    sysp = persona_prompt("Sage") + (
        " Propose the next high-leverage work. Output ONLY a numbered list of "
        f"{propose} short, concrete, NON-human-gated tasks (no money/sending/publishing). "
        "Each one line, imperative, doable by a counselor drafting to the outbox.")
    prompt = (f"Focus (the law): {focus}\nOpen tasks on the board: {open_n}\nRecent activity:\n"
              + "\n".join(recent[-20:]) + f"\n\nThe {propose} best next tasks:")
    text, mode = llm(COUNSELORS["Sage"]["provider"], COUNSELORS["Sage"]["model"], sysp, prompt)
    text = strip_reasoning(text)
    cand = []
    for line in text.splitlines():
        line = _re.sub(r"^[\s\-*\d.)]+", "", line).strip()
        if 8 <= len(line) <= 140 and not any(
                g in line.lower() for g in ("human", "money", "send", "pay", "[need", "publish")):
            cand.append(line)
        if len(cand) >= propose:
            break
    for c in cand:
        add_task(f"[REFLECT] {c}", "reflect")
    ledger("reflect", f"proposed {len(cand)} next tasks (mode={mode})", "reflect")
    _log.info("reflect: proposed %d tasks (mode=%s)", len(cand), mode)
    return {"proposed": cand, "mode": mode}


def autopilot(rounds: int = 6, workers: int = 3) -> dict:
    """ONE-COMMAND AUTONOMY: pre-flight health → swarm → morning report → re-check.

    Composes the verified pieces into a single 'run the whole cycle' entrypoint, the way a
    scheduler or another agent would drive it. Cost-safe by default (forces MINDBOT_NO_SONIC
    unless already set) so it never wakes the billed fleet. Honors the PAUSE flag. Drafts only.
    """
    os.environ.setdefault("MINDBOT_NO_SONIC", "1")   # never surprise-bill from autopilot
    before = health()
    if before["paused"]:
        _log.info("autopilot: paused — standing down")
        return {"ok": False, "reason": "paused", "health": before}
    _log.info("autopilot: launching (rounds=%d workers=%d ready=%s)", rounds, workers, before["ready"])
    ledger("autopilot_start", f"rounds={rounds} workers={workers} ready={before['ready']}", "autopilot")
    sw = swarm(workers=workers, rounds=rounds)
    report = morning_report()
    after = health()
    ledger("autopilot_done",
           f"{sw['pulses']} pulses -> {len(sw['produced'])} drafts; report={os.path.basename(report)}",
           "autopilot")
    _log.info("autopilot: done — %d pulses, %d drafts", sw["pulses"], len(sw["produced"]))
    return {"ok": True, "pulses": sw["pulses"], "produced": sw["produced"],
            "report": report, "ready_before": before["ready"], "ready_after": after["ready"],
            "compute_fund": after["compute_fund"]}
