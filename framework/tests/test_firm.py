"""THE FIRM — the hierarchical swarm. Mocked model calls: no network, no spend.

What must hold:
  * the pyramid SHAPE — 1 orchestrator call, N managers, N*M workers, 1 janitor
  * every rank uses ITS OWN model (the whole point — not one model wearing four hats)
  * the cost report proves the pyramid and beats an all-orchestrator flat swarm
"""
import unittest

from mindbot_pipeline import firm


class TestFirm(unittest.TestCase):
    def setUp(self):
        self.seen = []            # (model, system-prompt-prefix) per call, in order
        self._llm = firm.llm
        self._ledger = firm.ledger
        self._log = firm._log

        def fake_llm(provider, model, system, prompt):
            self.seen.append(model)
            if "ORCHESTRATOR" in system:
                return "Division one\nDivision two\nDivision three", "mock"
            if "MANAGER" in system:
                return "Task alpha\nTask beta", "mock"
            if "WORKER" in system:
                return "a concrete deliverable", "mock"
            return "merged deliverable", "mock"

        firm.llm = fake_llm
        firm.ledger = lambda *a, **k: None
        import logging
        quiet = logging.getLogger("mindbot.test.firm")
        quiet.addHandler(logging.NullHandler())
        quiet.propagate = False
        firm._log = quiet

    def tearDown(self):
        firm.llm, firm.ledger, firm._log = self._llm, self._ledger, self._log

    def test_pyramid_shape_and_model_per_rank(self):
        f = firm.Firm()
        rec = f.run("test goal", divisions=3, tasks=2)
        ranks = [c["rank"] for c in f.calls]
        self.assertEqual(ranks.count("orchestrator"), 1)          # the expensive model runs once
        self.assertEqual(ranks.count("manager"), 3)               # one per division
        self.assertEqual(ranks.count("worker"), 6)                # divisions x tasks
        self.assertEqual(ranks.count("janitor"), 1)               # one cleanup pass
        # each rank used its OWN distinct model
        by_rank = {c["rank"]: c["model"] for c in f.calls}
        self.assertEqual(len({by_rank[r] for r in ("orchestrator", "manager", "worker", "janitor")}), 4)
        self.assertEqual(by_rank["orchestrator"], "anthropic/claude-opus-5")
        self.assertEqual(by_rank["worker"], "openai/gpt-5.6-terra")
        self.assertEqual(rec["final"], "merged deliverable")

    def test_report_proves_the_cost_pyramid(self):
        f = firm.Firm()
        f.run("test goal", divisions=3, tasks=2)
        rep = f.report()
        self.assertEqual(rep["total_calls"], 11)
        # a flat swarm (everything on the orchestrator model) must cost strictly more
        self.assertGreater(rep["flat_swarm_cost"], rep["total_cost"])
        self.assertGreater(rep["saved_pct"], 0)
        self.assertEqual([b["rank"] for b in rep["by_rank"]],
                         ["orchestrator", "manager", "worker", "janitor"])

    def test_model_override(self):
        f = firm.Firm(models={"worker": {"model": "custom/cheap-model"}})
        f.run("test goal", divisions=1, tasks=1)
        self.assertIn("custom/cheap-model", [c["model"] for c in f.calls])


if __name__ == "__main__":
    unittest.main()
