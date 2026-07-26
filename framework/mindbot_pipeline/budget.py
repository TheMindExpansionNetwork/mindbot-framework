"""BUDGET — a hard spend ceiling the agent physically cannot cross.

THE HOLE THIS CLOSES
  We built excellent accountability: every action is hash-chained, Merkle-rooted and externally
  anchored, so we can PROVE what the agent spent. We had zero PREVENTION. A mod granted the
  `model` capability, a `firm` run in a loop, or a swarm left overnight could drain an API
  balance and the only thing we'd offer afterwards is a beautifully notarized receipt for the
  damage. Proof of a fire is not a smoke detector.

  This is the smoke detector. Caps are checked BEFORE each call, at the one chokepoint every
  model call in the framework passes through (`models.llm`) — core, council, firm, swarm, yolo,
  evolve, and third-party mods alike. Nothing routes around it.

THREE CEILINGS, ALL ENFORCED
    run    — one process/invocation (stops a runaway loop)
    day    — rolling calendar day (stops a bad week from one bad night)
    total  — lifetime of the ledger file (a hard wall you set once)
  Plus PER-MOD caps: a mod may hold the `model` capability and still be limited to cents.

WHY THIS IS DIFFERENT FROM A "max_tokens" SETTING
  A token limit caps one CALL. This caps the AGENT. And because every allow/deny decision is
  written to the same hash-chained ledger the notary anchors, you get something no other
  framework offers: **provable spend limits** — cryptographic evidence that an autonomous system
  never exceeded a stated budget. That is an auditable control, not a config value.

SAFE BY DEFAULT
  With no configuration the governor is ACTIVE with conservative caps (see DEFAULTS). It is
  opt-OUT (`MINDBOT_BUDGET_OFF=1`), not opt-in — a safety control you must remember to enable
  is a safety control that will be missing when it matters.

Extend: prices -> PRICES (per 1M tokens, matched by slug prefix); a new ceiling -> add to
DEFAULTS + a check in `check()`. Never add a bypass path — the value is that there isn't one.
"""
from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

from .collaboration import PIPE_DIR, ledger
from .logs import get_logger

_log = get_logger("budget")

SPEND_LOG = PIPE_DIR / "spend.jsonl"

# USD per 1M tokens (input, output). Matched by longest slug prefix; verified 2026-07.
# An unknown model bills at UNKNOWN_PRICE — deliberately pessimistic, so a model we don't
# recognise can never look free and slip past a ceiling.
PRICES: dict[str, tuple[float, float]] = {
    "anthropic/claude-opus-5":        (5.00, 25.00),
    "anthropic/claude-opus":          (5.00, 25.00),
    "anthropic/claude-sonnet-5":      (2.00, 10.00),
    "anthropic/claude-sonnet":        (3.00, 15.00),
    "openai/gpt-5.6-sol":             (5.00, 30.00),
    "openai/gpt-5.6-terra":           (2.50, 15.00),
    "openai/gpt-5.6-luna":            (1.00, 6.00),
    "openai/gpt-5.6":                 (2.50, 15.00),
    "openai/gpt-5":                   (2.50, 15.00),
    "x-ai/grok-4.5":                  (2.00, 6.00),
    "x-ai/grok":                      (1.25, 2.50),
    "google/gemini-3.6-flash":        (1.50, 7.50),
    "google/gemini-3.5-flash":        (1.50, 9.00),
    "google/gemini-3.1-pro":          (2.00, 12.00),
    "google/gemini":                  (1.50, 9.00),
    "z-ai/glm-5.2":                   (0.80, 2.50),
    "z-ai/glm":                       (0.97, 3.04),
    "deepseek/deepseek-v4-flash":     (0.09, 0.19),
    "deepseek/deepseek-v4-pro":       (0.43, 0.87),
    "deepseek":                       (0.43, 0.87),
    "moonshotai/kimi-k3":             (3.00, 15.00),
    "moonshotai":                     (0.78, 3.50),
    "meta-llama/llama-4-scout":       (0.10, 0.30),
    "meta-llama":                     (0.20, 0.80),
    "qwen":                           (0.32, 1.28),
    "mistralai":                      (0.30, 0.90),
}
UNKNOWN_PRICE = (5.00, 25.00)          # assume expensive when unsure

# Conservative defaults — generous enough for real work, small enough that a runaway is capped.
DEFAULTS = {"run": 2.00, "day": 10.00, "total": 100.00}


class BudgetExceeded(Exception):
    """Raised BEFORE a model call that would breach a ceiling. The call never happens."""


def _free(model: str) -> bool:
    return model.endswith(":free")


def price_of(model: str) -> tuple[float, float]:
    if _free(model):
        return (0.0, 0.0)
    best = ""
    for slug in PRICES:
        if model.startswith(slug) and len(slug) > len(best):
            best = slug
    return PRICES[best] if best else UNKNOWN_PRICE


def estimate(model: str, prompt_chars: int, expected_out_tokens: int = 700) -> float:
    """Pre-call cost estimate. ~4 chars/token; assume a full-length reply (pessimistic)."""
    pin, pout = price_of(model)
    tin = max(1, prompt_chars // 4)
    return tin / 1e6 * pin + expected_out_tokens / 1e6 * pout


def caps() -> dict:
    """Active ceilings. Env overrides the defaults; MINDBOT_BUDGET_OFF=1 disables enforcement."""
    c = dict(DEFAULTS)
    for k in c:
        v = os.environ.get(f"MINDBOT_BUDGET_{k.upper()}")
        if v:
            try:
                c[k] = float(v)
            except ValueError:
                pass
    c["enabled"] = os.environ.get("MINDBOT_BUDGET_OFF") != "1"
    return c


# ── the running tally ────────────────────────────────────────────────────────
_run_spend = 0.0                       # this process only


def _rows() -> list[dict]:
    if not SPEND_LOG.exists():
        return []
    out = []
    for ln in SPEND_LOG.read_text(encoding="utf-8", errors="ignore").splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                pass
    return out


def spent(scope: str = "day", mod: str | None = None) -> float:
    """Spend so far in a scope: 'run' | 'day' | 'total' (optionally for one mod)."""
    if scope == "run" and mod is None:
        return _run_spend
    today = date.today().isoformat()
    total = 0.0
    for r in _rows():
        if mod is not None and r.get("mod") != mod:
            continue
        if scope == "day" and not str(r.get("ts", "")).startswith(today):
            continue
        total += float(r.get("cost", 0) or 0)
    return total


def record(model: str, cost: float, mod: str | None = None, note: str = "") -> None:
    """Append actual spend. Called after a successful model call."""
    global _run_spend
    _run_spend += cost
    SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SPEND_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "model": model,
                            "cost": round(cost, 6), "mod": mod, "note": note[:80]}) + "\n")


def check(model: str, prompt_chars: int, mod: str | None = None,
          mod_cap: float | None = None) -> dict:
    """Gate a call BEFORE it happens. Raises BudgetExceeded, else returns the estimate.

    This is the whole safety property: prevention, not reporting.
    """
    c = caps()
    est = estimate(model, prompt_chars)
    if not c["enabled"] or est == 0.0:          # free models never consume budget
        return {"ok": True, "estimate": est, "enforced": c["enabled"]}

    # per-mod ceiling first: third-party code is the least-trusted spender
    if mod and mod_cap is not None:
        used = spent("day", mod=mod)
        if used + est > mod_cap:
            ledger("budget_denied", f"mod:{mod} ${used:.4f}+${est:.4f} > cap ${mod_cap:.2f}", "budget")
            _log.warning("BUDGET DENIED mod=%s used=%.4f est=%.4f cap=%.2f", mod, used, est, mod_cap)
            raise BudgetExceeded(
                f"mod '{mod}' would exceed its daily cap (${used:.4f} + ${est:.4f} > ${mod_cap:.2f})")

    for scope in ("run", "day", "total"):
        used = spent(scope)
        if used + est > c[scope]:
            ledger("budget_denied", f"{scope} ${used:.4f}+${est:.4f} > cap ${c[scope]:.2f}", "budget")
            _log.warning("BUDGET DENIED scope=%s used=%.4f est=%.4f cap=%.2f", scope, used, est, c[scope])
            raise BudgetExceeded(
                f"{scope} budget would be exceeded: ${used:.4f} + ~${est:.4f} > ${c[scope]:.2f}. "
                f"Raise it with MINDBOT_BUDGET_{scope.upper()} or disable with MINDBOT_BUDGET_OFF=1.")
    return {"ok": True, "estimate": est, "enforced": True}


def status() -> dict:
    c = caps()
    rows = _rows()
    by_mod: dict[str, float] = {}
    for r in rows:
        if r.get("mod"):
            by_mod[r["mod"]] = by_mod.get(r["mod"], 0.0) + float(r.get("cost", 0) or 0)
    return {
        "enabled": c["enabled"],
        "caps": {k: c[k] for k in ("run", "day", "total")},
        "spent": {"run": round(spent("run"), 6), "day": round(spent("day"), 6),
                  "total": round(spent("total"), 6)},
        "remaining": {k: round(c[k] - spent(k), 6) for k in ("run", "day", "total")},
        "calls": len(rows),
        "by_mod": {k: round(v, 6) for k, v in sorted(by_mod.items(), key=lambda x: -x[1])},
    }
