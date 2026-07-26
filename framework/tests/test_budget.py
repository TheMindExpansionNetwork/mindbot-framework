"""BUDGET — the hard ceiling. The only tests that matter are the ones proving it BLOCKS.

A spend cap that reports overspending is an invoice. A spend cap that prevents the call is a
control. These assert prevention: the call never happens, the denial is recorded, and there is
no path around the chokepoint.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from mindbot_pipeline import budget


class TestBudget(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self._saved = (budget.SPEND_LOG, budget.ledger, budget._run_spend)
        budget.SPEND_LOG = self._tmp / "spend.jsonl"
        self.events = []
        budget.ledger = lambda ev, d, a="framework": self.events.append((ev, d))
        budget._run_spend = 0.0
        self._env = {k: os.environ.get(k) for k in
                     ("MINDBOT_BUDGET_RUN", "MINDBOT_BUDGET_DAY",
                      "MINDBOT_BUDGET_TOTAL", "MINDBOT_BUDGET_OFF")}
        for k in self._env:
            os.environ.pop(k, None)

    def tearDown(self):
        budget.SPEND_LOG, budget.ledger, budget._run_spend = self._saved
        for k, v in self._env.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        shutil.rmtree(self._tmp, ignore_errors=True)

    # ── pricing ──────────────────────────────────────────────────────────────
    def test_price_lookup_prefers_longest_prefix(self):
        self.assertEqual(budget.price_of("anthropic/claude-opus-5"), (5.00, 25.00))
        self.assertEqual(budget.price_of("deepseek/deepseek-v4-flash"), (0.09, 0.19))
        self.assertEqual(budget.price_of("openai/gpt-5.6-luna"), (1.00, 6.00))

    def test_free_models_are_free_and_never_gated(self):
        self.assertEqual(budget.price_of("nvidia/nemotron-3-ultra-550b-a55b:free"), (0.0, 0.0))
        os.environ["MINDBOT_BUDGET_DAY"] = "0"          # zero budget…
        r = budget.check("nvidia/nemotron-3-ultra:free", 10_000)
        self.assertTrue(r["ok"])                        # …a free model still runs

    def test_unknown_model_is_billed_pessimistically(self):
        """An unrecognised slug must never look free, or it becomes the bypass."""
        self.assertEqual(budget.price_of("who/knows-9000"), budget.UNKNOWN_PRICE)

    # ── THE HEADLINE: it blocks ──────────────────────────────────────────────
    def test_exceeding_a_cap_raises_before_the_call(self):
        os.environ["MINDBOT_BUDGET_DAY"] = "0.001"
        with self.assertRaises(budget.BudgetExceeded):
            budget.check("anthropic/claude-opus-5", 40_000)
        self.assertIn("budget_denied", [e[0] for e in self.events])   # the denial is recorded

    def test_run_cap_stops_a_runaway_loop(self):
        os.environ["MINDBOT_BUDGET_RUN"] = "0.05"
        blocked = False
        for _ in range(200):                            # simulate a runaway
            try:
                budget.check("anthropic/claude-opus-5", 8_000)
                budget.record("anthropic/claude-opus-5", 0.01)
            except budget.BudgetExceeded:
                blocked = True
                break
        self.assertTrue(blocked, "a runaway loop was never stopped")
        self.assertLess(budget.spent("run"), 0.10)      # bounded near the cap

    def test_spend_accumulates_across_scopes(self):
        budget.record("openai/gpt-5.6-terra", 0.02)
        budget.record("openai/gpt-5.6-terra", 0.03)
        self.assertAlmostEqual(budget.spent("day"), 0.05, places=6)
        self.assertAlmostEqual(budget.spent("total"), 0.05, places=6)
        self.assertAlmostEqual(budget.spent("run"), 0.05, places=6)

    # ── per-mod ceilings: third-party code is the least-trusted spender ──────
    def test_mod_cap_is_enforced_independently(self):
        # 0.24 spent + a ~$0.024 estimate (1250 in / 700 out on opus-5) > the 0.25 cap
        budget.record("anthropic/claude-opus-5", 0.24, mod="greedy")
        with self.assertRaises(budget.BudgetExceeded):
            budget.check("anthropic/claude-opus-5", 5_000, mod="greedy", mod_cap=0.25)
        # a different mod is unaffected by its neighbour's spending
        self.assertTrue(budget.check("anthropic/claude-opus-5", 100, mod="polite", mod_cap=0.25)["ok"])

    def test_a_mod_cannot_raise_its_own_ceiling(self):
        from mindbot_pipeline.mods import ModAPI
        self.assertEqual(ModAPI("x", ["model"], spend_cap=999.0).spend_cap,
                         ModAPI.DEFAULT_MOD_SPEND_CAP)          # clamped down
        self.assertEqual(ModAPI("x", ["model"], spend_cap=0.05).spend_cap, 0.05)  # may lower

    # ── opt-out is explicit ──────────────────────────────────────────────────
    def test_enforcement_is_on_by_default_and_opt_out_is_explicit(self):
        self.assertTrue(budget.caps()["enabled"])
        os.environ["MINDBOT_BUDGET_OFF"] = "1"
        self.assertFalse(budget.caps()["enabled"])
        os.environ["MINDBOT_BUDGET_DAY"] = "0"
        self.assertTrue(budget.check("anthropic/claude-opus-5", 99_999)["ok"])   # off = allowed

    def test_status_shape(self):
        budget.record("z-ai/glm-5.2", 0.01, mod="m1")
        s = budget.status()
        for k in ("enabled", "caps", "spent", "remaining", "calls", "by_mod"):
            self.assertIn(k, s)
        self.assertIn("m1", s["by_mod"])


class TestChokepoint(unittest.TestCase):
    """llm() must degrade to mode='budget' rather than raise — the loop cannot crash at 3am."""

    def test_llm_returns_budget_mode_instead_of_raising(self):
        from mindbot_pipeline import models
        saved = os.environ.get("MINDBOT_BUDGET_DAY")
        os.environ["MINDBOT_BUDGET_DAY"] = "0.000001"
        try:
            text, mode = models.llm("anthropic", "anthropic/claude-opus-5", "sys", "x" * 8000)
            self.assertEqual(mode, "budget")
            self.assertIn("[NEED: budget]", text)
        finally:
            os.environ.pop("MINDBOT_BUDGET_DAY", None)
            if saved is not None:
                os.environ["MINDBOT_BUDGET_DAY"] = saved


if __name__ == "__main__":
    unittest.main()
