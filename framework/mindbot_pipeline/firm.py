"""THE FIRM — a hierarchical multi-model swarm. An org chart, in software.

Every other "agent swarm" is FLAT: N copies of one model, all doing the same thing. A real
organization is not flat — it has an executive who decides, managers who decompose, workers who
execute, and support staff who clean up. THE FIRM maps each of those layers onto a DIFFERENT
model, chosen for what that rank actually needs, and runs them as one pipeline.

    RANK          MODEL                 WHY THAT MODEL              WHAT IT DOES
    ─────────────────────────────────────────────────────────────────────────────────────
    ORCHESTRATOR  anthropic/claude-opus-5   deepest judgment        strategy; splits the goal
                                            (most expensive)        into divisions
    MANAGER       openai/gpt-5.6-sol        strong reasoning        takes ONE division, turns
                                                                    it into concrete tasks
    WORKER        openai/gpt-5.6-terra      balanced + fast         does ONE task, produces
                                            (the bulk of calls)     the actual deliverable
    JANITOR       openai/gpt-5.6-luna       cheapest capable        QA, cleanup, dedupe,
                                                                    formatting, final polish

WHY THIS IS BETTER THAN A FLAT SWARM
  - COST: the expensive model is called ~once; the cheap model absorbs the volume. Spend is
    shaped like a pyramid, not a rectangle. `report()` proves it per rank.
  - QUALITY: judgment work goes to a judgment model; grunt work goes to a fast one. Neither is
    mismatched to its task.
  - PARALLELISM: managers fan out concurrently, and each manager's workers fan out again — the
    tree widens at exactly the layer where the work is independent.
  - AUDITABILITY: every rank's output is captured in the run record, so you can see WHERE a
    result came from, not just that it appeared.

CONSTITUTION: unchanged. The Firm produces DRAFTS. Nothing sends, charges, or publishes.

Extend: add a rank -> add it to RANKS and give it a stage in `run()`; change a rank's model ->
edit RANKS (or override at call time with `models=`); the whole pyramid is data, not code.

CLI:  mindbot firm "<goal>" [--divisions 3] [--tasks 2]
"""
from __future__ import annotations

import concurrent.futures as _cf
import json
import os
import re
import time

from .collaboration import PIPE_DIR, ledger, now
from .logs import get_logger
from .models import llm, strip_reasoning

_log = get_logger("firm")

# The org chart. Model per rank + the price we bill it at (USD per 1M tokens, in/out) so the
# run report can prove the cost pyramid. Prices verified 2026-07-25 (see docs/MODEL_LINEUP.md).
RANKS: dict[str, dict] = {
    "orchestrator": {"model": "anthropic/claude-opus-5", "provider": "anthropic",
                     "in": 5.00, "out": 25.00, "title": "Orchestrator"},
    "manager":      {"model": "openai/gpt-5.6-sol", "provider": "openai",
                     "in": 5.00, "out": 30.00, "title": "Manager"},
    "worker":       {"model": "openai/gpt-5.6-terra", "provider": "openai",
                     "in": 2.50, "out": 15.00, "title": "Worker"},
    "janitor":      {"model": "openai/gpt-5.6-luna", "provider": "openai",
                     "in": 1.00, "out": 6.00, "title": "Janitor"},
}

OUTBOX = PIPE_DIR / "outbox"
RUNS = PIPE_DIR / "firm_runs"


def _est_tokens(*parts: str) -> int:
    """Rough token estimate (~4 chars/token) — enough to shape the cost report."""
    return max(1, sum(len(p) for p in parts) // 4)


class Firm:
    """One hierarchical run. Holds the ledger of every call so the report can prove the pyramid."""

    def __init__(self, models: dict | None = None):
        # allow per-rank model overrides without touching the class default
        self.ranks = {k: {**v, **(models or {}).get(k, {})} for k, v in RANKS.items()}
        self.calls: list[dict] = []

    # ── one call at a given rank, fully accounted ────────────────────────────
    def ask(self, rank: str, system: str, prompt: str, label: str = "") -> str:
        spec = self.ranks[rank]
        t0 = time.time()
        text, mode = llm(spec["provider"], spec["model"], system, prompt)
        text = strip_reasoning(text)
        tin, tout = _est_tokens(system, prompt), _est_tokens(text)
        # A budget-denied call never reached a provider, so it costs nothing. Billing it would
        # make the run report (and the "% saved vs flat" claim) quietly wrong.
        blocked = mode == "budget"

        # BILL WHAT ANSWERED, NOT WHAT WE ASKED FOR.
        #
        # This used to price every call from RANKS[rank] — the model we INTENDED to use. But
        # the router falls back: MINDBOT_FREE overrides a paid pin, a rate-limited slug rolls
        # to the next, an endpoint drops to template mode. Whenever that happens the intended
        # price is fiction.
        #
        # Measured, and the whole reason this exists: a run whose calls ALL landed on
        # `nvidia/nemotron-3-ultra-550b-a55b:free` reported "$0.11838 · saved 55.2% vs a flat
        # swarm". The true cost was $0.00 and the saving was meaningless — a comparison between
        # two prices, neither of which was paid. A cost report that invents its own numbers is
        # exactly the overclaim this project exists to argue against, and it was sitting in the
        # one command whose entire pitch IS the cost table.
        #
        # `mode` carries the slug that actually answered ("openrouter:<slug>"), so price from
        # that: free slugs and self-hosted endpoints cost nothing; known slugs use the real
        # price table; an unrecognised slug falls back to the rank price, with `priced_from`
        # recording which of those happened so the report can say so out loud.
        served = mode.split(":", 1)[1] if ":" in mode else mode
        if blocked or mode == "template" or served.endswith(":free") \
                or mode.startswith(("modal:", "sonic")):
            cost, priced_from = 0.0, "free/self-hosted"
        else:
            from . import budget as _b
            pin, pout = _b.price_of(served)
            if (pin, pout) == _b.UNKNOWN_PRICE:
                pin, pout, priced_from = spec["in"], spec["out"], "rank (slug unknown)"
            else:
                priced_from = "actual slug"
            cost = tin / 1e6 * pin + tout / 1e6 * pout

        self.calls.append({
            "rank": rank, "title": spec["title"], "model": spec["model"], "label": label,
            "served_by": served, "priced_from": priced_from,
            "mode": mode, "secs": round(time.time() - t0, 2), "blocked": blocked,
            "tok_in": 0 if blocked else tin, "tok_out": 0 if blocked else tout, "cost": cost,
        })
        _log.info("firm %-12s %-24s %5.1fs $%0.5f  %s", rank, spec["model"], time.time() - t0, cost, label[:40])
        return text

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _lines(text: str, n: int) -> list[str]:
        """Parse a numbered/bulleted list into clean lines (models love to decorate)."""
        out = []
        for raw in text.splitlines():
            s = re.sub(r"^[\s\-*•\d.)\]]+", "", raw).strip()
            if 6 <= len(s) <= 200:
                out.append(s)
            if len(out) >= n:
                break
        return out

    # ── the pipeline ─────────────────────────────────────────────────────────
    def run(self, goal: str, divisions: int = 3, tasks: int = 2) -> dict:
        """ORCHESTRATOR → MANAGERs (parallel) → WORKERs (parallel) → JANITOR.

        Returns the full run record: every rank's output plus the cost report.
        """
        t0 = time.time()
        ledger("firm_start", f"{goal[:70]} (div={divisions} tasks={tasks})", "firm")
        _log.info("FIRM START: %s", goal[:80])

        # 1) ORCHESTRATOR — the only call to the most expensive model.
        strategy = self.ask(
            "orchestrator",
            "You are the ORCHESTRATOR of an AI firm. Break the goal into exactly "
            f"{divisions} independent DIVISIONS of work. Output ONLY {divisions} lines, one per "
            "division: a short imperative title (under 12 words). No preamble, no numbering.",
            f"GOAL: {goal}", "split the goal")
        divs = self._lines(strategy, divisions) or [goal]

        # 2) MANAGERS — one per division, in parallel. Each turns a division into tasks.
        def manage(div: str) -> dict:
            plan = self.ask(
                "manager",
                "You are a MANAGER in an AI firm. Turn your division into exactly "
                f"{tasks} concrete, independently-doable TASKS. Output ONLY {tasks} lines, one "
                "task each, imperative, under 18 words. No preamble, no numbering.",
                f"OVERALL GOAL: {goal}\nYOUR DIVISION: {div}", f"plan: {div[:38]}")
            return {"division": div, "tasks": self._lines(plan, tasks) or [div]}

        with _cf.ThreadPoolExecutor(max_workers=min(6, len(divs))) as ex:
            plans = list(ex.map(manage, divs))

        # 3) WORKERS — every task from every division, all in parallel. The bulk of the calls.
        jobs = [(p["division"], t) for p in plans for t in p["tasks"]]

        def work(job) -> dict:
            div, task = job
            out = self.ask(
                "worker",
                "You are a WORKER in an AI firm. Do the task and produce the actual deliverable "
                "— concrete and usable, not a plan about doing it. Under 160 words. No preamble.",
                f"OVERALL GOAL: {goal}\nDIVISION: {div}\nYOUR TASK: {task}", f"do: {task[:38]}")
            return {"division": div, "task": task, "output": out}

        with _cf.ThreadPoolExecutor(max_workers=min(8, len(jobs))) as ex:
            results = list(ex.map(work, jobs))

        # 4) JANITOR — cheapest model does the cleanup pass: dedupe, order, polish.
        bundle = "\n\n".join(f"[{r['division']}] {r['task']}\n{r['output']}" for r in results)
        final = self.ask(
            "janitor",
            "You are the JANITOR of an AI firm: the cleanup and QA pass. Merge the workers' "
            "outputs into ONE clean, deduplicated, well-ordered deliverable in markdown. Cut "
            "repetition and filler. Keep every concrete detail. No preamble about what you did.",
            f"GOAL: {goal}\n\nWORKER OUTPUTS:\n{bundle}", "merge + polish")

        rec = {
            "goal": goal, "started": now(), "secs": round(time.time() - t0, 1),
            "divisions": divs, "plans": plans, "results": results, "final": final,
            "report": self.report(), "calls": self.calls,
        }
        RUNS.mkdir(parents=True, exist_ok=True)
        stamp = now().replace(" ", "-").replace(":", "")
        (RUNS / f"{stamp}_firm.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
        OUTBOX.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in goal[:44])
        (OUTBOX / f"{stamp}_FIRM_{safe}.md").write_text(
            f"# {goal}\n\n*Produced by THE FIRM — {len(self.calls)} calls across 4 ranks in "
            f"{rec['secs']}s. Draft only; a human approves.*\n\n{final}\n", encoding="utf-8")
        ledger("firm_done", f"{goal[:60]} — {len(self.calls)} calls, ${rec['report']['total_cost']:.4f}", "firm")
        _log.info("FIRM DONE: %d calls, $%.4f, %.1fs", len(self.calls), rec["report"]["total_cost"], rec["secs"])
        return rec

    # ── the proof: cost + call shape per rank ────────────────────────────────
    def report(self) -> dict:
        by: dict[str, dict] = {}
        for c in self.calls:
            b = by.setdefault(c["rank"], {"rank": c["rank"], "title": c["title"],
                                          "model": c["model"], "calls": 0, "cost": 0.0,
                                          "tok_in": 0, "tok_out": 0, "secs": 0.0})
            b["calls"] += 1
            b["cost"] += c["cost"]
            b["tok_in"] += c["tok_in"]
            b["tok_out"] += c["tok_out"]
            b["secs"] += c["secs"]
        total = sum(b["cost"] for b in by.values())
        for b in by.values():
            b["cost"] = round(b["cost"], 6)
            b["pct"] = round(100 * b["cost"] / total, 1) if total else 0.0
        blocked = sum(1 for c in self.calls if c.get("blocked"))

        # DID WE ACTUALLY RUN THE ORG CHART WE ADVERTISED?
        # If the router substituted models, the tiering claim is about a run that did not
        # happen, and the report has to say so rather than quietly print a savings figure.
        served = {c.get("served_by", "?") for c in self.calls}
        intended = {self.ranks[c["rank"]]["model"] for c in self.calls}
        substituted = sorted(s for s in served if s not in intended)
        all_free = bool(self.calls) and all(c["cost"] == 0 for c in self.calls)

        # What the same work would have cost with EVERY call on the orchestrator model.
        # Only meaningful when the run was actually billed — comparing two prices you did not
        # pay is not a saving, it is arithmetic.
        o = self.ranks["orchestrator"]
        flat = sum(c["tok_in"] / 1e6 * o["in"] + c["tok_out"] / 1e6 * o["out"] for c in self.calls)
        return {
            "by_rank": [by[r] for r in ("orchestrator", "manager", "worker", "janitor") if r in by],
            "total_calls": len(self.calls),
            "blocked_by_budget": blocked,
            "total_cost": round(total, 6),
            "flat_swarm_cost": round(flat, 6),
            "saved_vs_flat": round(flat - total, 6) if not all_free else 0.0,
            "saved_pct": round(100 * (flat - total) / flat, 1) if (flat and not all_free) else 0.0,
            # Honesty fields — the CLI prints these instead of a savings claim when they fire.
            "served_by": sorted(served),
            "substituted_models": substituted,
            "ran_as_designed": not substituted,
            "all_calls_free": all_free,
            "cost_is_real": not all_free and not substituted,
        }


def run_firm(goal: str, divisions: int = 3, tasks: int = 2, models: dict | None = None) -> dict:
    """Convenience entry point used by the CLI."""
    os.environ.setdefault("MINDBOT_NO_SONIC", "1")   # never wake the billed GPU fleet from here
    return Firm(models).run(goal, divisions=divisions, tasks=tasks)
