"""Autonomous-readiness: operational logging, the health self-check, and swarm resilience —
the things that make an UNATTENDED run safe (observable + crash-tolerant)."""
import logging
import os
import threading
import unittest

from mindbot_pipeline import logs, models, nucleus


class TestLogs(unittest.TestCase):
    def test_logger_writes_and_recent_errors_is_a_list(self):
        log = logs.get_logger("test")
        log.warning("unit-test warning marker")
        self.assertIsInstance(logs.recent_errors(3), list)


class TestHealth(unittest.TestCase):
    def test_health_returns_a_readiness_dict(self):
        h = nucleus.health()
        for k in ("ready", "paused", "pulses", "board", "compute_fund", "recent_errors"):
            self.assertIn(k, h)
        self.assertIsInstance(h["ready"], bool)
        self.assertIn("claimable", h["board"])


class TestSwarmResilience(unittest.TestCase):
    def test_worker_survives_a_crashing_pulse(self):
        calls, lock = {"n": 0}, threading.Lock()

        def boom(agent=None):
            with lock:
                calls["n"] += 1
            raise RuntimeError("boom")  # every pulse explodes

        saved = (nucleus.pulse, nucleus.ledger, nucleus._log)
        nucleus.pulse = boom
        nucleus.ledger = lambda *a, **k: None
        silent = logging.getLogger("mindbot.test.silent")
        silent.addHandler(logging.NullHandler())
        silent.propagate = False
        nucleus._log = silent
        try:
            res = nucleus.swarm(workers=2, rounds=6, idle_stop=2)  # must NOT hang or raise
        finally:
            nucleus.pulse, nucleus.ledger, nucleus._log = saved
        self.assertIn("pulses", res)
        self.assertGreater(calls["n"], 0)   # workers kept pulsing despite every pulse crashing


class TestAutopilot(unittest.TestCase):
    """autopilot composes verified pieces (health -> swarm -> report) and honors PAUSE."""

    def _silence(self):
        lg = logging.getLogger("mindbot.test.autopilot")
        lg.addHandler(logging.NullHandler())
        lg.propagate = False
        return lg

    def test_autopilot_runs_the_full_cycle(self):
        saved = (nucleus.swarm, nucleus.morning_report, nucleus.health, nucleus.ledger, nucleus._log)
        env = os.environ.get("MINDBOT_NO_SONIC")
        nucleus.swarm = lambda **k: {"pulses": 3, "produced": ["a", "b"]}
        nucleus.morning_report = lambda: "C:/x/MORNING_REPORT.md"
        nucleus.health = lambda: {"paused": False, "ready": True, "compute_fund": 0.0}
        nucleus.ledger = lambda *a, **k: None
        nucleus._log = self._silence()
        try:
            res = nucleus.autopilot(rounds=3, workers=2)
        finally:
            (nucleus.swarm, nucleus.morning_report, nucleus.health,
             nucleus.ledger, nucleus._log) = saved
            if env is None:
                os.environ.pop("MINDBOT_NO_SONIC", None)
        self.assertTrue(res["ok"])
        self.assertEqual(res["pulses"], 3)
        self.assertEqual(len(res["produced"]), 2)

    def test_autopilot_stands_down_when_paused(self):
        saved = (nucleus.health, nucleus._log)
        nucleus.health = lambda: {"paused": True, "ready": False}
        nucleus._log = self._silence()
        try:
            res = nucleus.autopilot()
        finally:
            (nucleus.health, nucleus._log) = saved
        self.assertFalse(res["ok"])
        self.assertEqual(res["reason"], "paused")


class TestEvolve(unittest.TestCase):
    """Self-improvement loop: proposes on GREEN, and dry_run reverts to leave a clean tree."""

    def test_evolve_proposes_and_dry_run_reverts(self):
        from mindbot_pipeline import harness
        reverted = {}
        saved = (harness.code_task, harness._revert,
                 nucleus.outbox_write, nucleus.ledger, nucleus._log)
        env = os.environ.get("MINDBOT_NO_SONIC")
        harness.code_task = lambda task, seat="Forge", max_steps=10: {
            "ok": True, "touched": ["framework/tests/test_x.py"], "summary": "added a test"}
        harness._revert = lambda touched: reverted.__setitem__("files", touched)
        nucleus.outbox_write = lambda *a, **k: None
        nucleus.ledger = lambda *a, **k: None
        lg = logging.getLogger("mindbot.test.evolve")
        lg.addHandler(logging.NullHandler())
        lg.propagate = False
        nucleus._log = lg
        try:
            res = nucleus.evolve(iterations=1, dry_run=True)
        finally:
            (harness.code_task, harness._revert,
             nucleus.outbox_write, nucleus.ledger, nucleus._log) = saved
            if env is None:
                os.environ.pop("MINDBOT_NO_SONIC", None)
        self.assertEqual(res["iterations"], 1)
        self.assertTrue(res["results"][0]["ok"])
        self.assertEqual(reverted.get("files"), ["framework/tests/test_x.py"])  # dry_run cleaned up


class TestReflect(unittest.TestCase):
    """Self-direction: parse the model's proposals into clean [REFLECT] board tasks."""

    def test_reflect_parses_proposals(self):
        from mindbot_pipeline import collaboration
        added = []
        saved = (nucleus.llm, nucleus.ledger, nucleus._log, collaboration.add_task)
        env = os.environ.get("MINDBOT_NO_SONIC")
        nucleus.llm = lambda *a, **k: (
            "1. Draft a launch tweet for the storefront\n"
            "2. Add a stdlib test for fleet status\n"
            "3. Write an onboarding FAQ", "mock")
        nucleus.ledger = lambda *a, **k: None
        collaboration.add_task = lambda text, agent="framework": added.append(text)
        lg = logging.getLogger("mindbot.test.reflect")
        lg.addHandler(logging.NullHandler())
        lg.propagate = False
        nucleus._log = lg
        try:
            r = nucleus.reflect(propose=3)
        finally:
            (nucleus.llm, nucleus.ledger, nucleus._log, collaboration.add_task) = saved
            if env is None:
                os.environ.pop("MINDBOT_NO_SONIC", None)
        self.assertEqual(len(r["proposed"]), 3)
        self.assertTrue(all(a.startswith("[REFLECT]") for a in added))
        self.assertNotIn("1.", r["proposed"][0])   # numbering stripped


class TestModelOverride(unittest.TestCase):
    """MINDBOT_MODEL pins the WHOLE council to one OpenRouter slug, beating per-seat defaults."""

    def test_override_pins_every_seat(self):
        from mindbot_pipeline import models
        seen = {}
        saved_post = models._openai_style
        saved_env = {k: os.environ.get(k) for k in
                     ("OPENROUTER_API_KEY", "MINDBOT_MODEL", "MINDBOT_SONIC_URL", "MINDBOT_FREE")}
        models._openai_style = lambda url, slug, system, prompt, key: (seen.update(slug=slug) or "hi")
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
        os.environ["MINDBOT_MODEL"] = "z-ai/glm-5.2"
        os.environ.pop("MINDBOT_SONIC_URL", None)
        os.environ.pop("MINDBOT_FREE", None)
        try:
            text, mode = models.llm("anthropic", "claude-fable-5", "sys", "hi")
        finally:
            models._openai_style = saved_post
            for k, v in saved_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.assertEqual(seen["slug"], "z-ai/glm-5.2")          # override beat the seat default
        self.assertEqual(mode, "openrouter:z-ai/glm-5.2")       # model rides in the mode for the ledger


class TestCostGuard(unittest.TestCase):
    """The invariant that keeps an unattended loop from surprise-billing: MINDBOT_NO_SONIC=1
    physically disables the (billed) GPU fleet, even when a fleet URL is configured."""

    def test_no_sonic_env_disables_the_fleet(self):
        saved = {k: os.environ.get(k) for k in ("MINDBOT_NO_SONIC", "MINDBOT_SONIC_URL")}
        os.environ["MINDBOT_SONIC_URL"] = "https://example.modal.run/v1"
        try:
            os.environ["MINDBOT_NO_SONIC"] = "1"
            self.assertEqual(models._sonic_url(), "")          # guard wins even with a URL set
            os.environ.pop("MINDBOT_NO_SONIC")
            self.assertTrue(models._sonic_url().endswith("/chat/completions"))  # else resolves normally
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
