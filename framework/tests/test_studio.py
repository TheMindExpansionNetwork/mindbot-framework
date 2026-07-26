"""STUDIO + COST GUARD — the two things that make this framework not-basic and not-expensive.

No test here makes a real model call. Every one stubs `_ask`, because a test suite that bills
you is a test suite you stop running — and this project is being built on a $5 budget.
"""
import os
import unittest
from pathlib import Path
from unittest import mock

from mindbot_pipeline import studio


class TestKindsAreReal(unittest.TestCase):
    """The first version of studio.py invented five counselors that were never on the roster.
    It surfaced as a bare KeyError three stages into a live, BILLED run."""

    def test_every_seat_and_critic_exists(self):
        from mindbot_pipeline.counselors import COUNSELORS
        for kind, spec in studio.KINDS.items():
            for seat in list(spec["seats"]) + [spec["critic"]]:
                self.assertIn(seat, COUNSELORS, f"{kind} names non-existent counselor {seat!r}")

    def test_the_import_time_guard_actually_fires(self):
        with mock.patch.dict(studio.KINDS, {"bogus": {"seats": ["Nobody"], "critic": "Sage"}}):
            with self.assertRaises(RuntimeError) as e:
                studio._validate_seats()
            self.assertIn("Nobody", str(e.exception))

    def test_critic_is_never_the_only_drafting_seat(self):
        """Self-review reliably returns 'looks great'. A separate seat disagrees usefully."""
        for kind, spec in studio.KINDS.items():
            self.assertNotEqual([spec["critic"]], list(spec["seats"]),
                                f"{kind}: the critic must not be the sole author")


class TestClassify(unittest.TestCase):
    def test_routes_work_to_the_right_pipeline(self):
        cases = {
            "write a python script to parse logs": "code",
            "build a landing page for the launch": "build",
            "should we use postgres or sqlite": "decide",
            "research the agent framework landscape": "research",
            "a short poem about the eclipse": "write",
        }
        for text, expected in cases.items():
            self.assertEqual(studio.classify(text), expected, f"misrouted: {text!r}")

    def test_code_beats_write(self):
        """'write a script' is a code task. Hint ORDER encodes this; a reorder would break it."""
        self.assertEqual(studio.classify("write a script that renames files"), "code")


class TestCritiqueLoop(unittest.TestCase):
    """The critique loop is the actual quality lever — and its failure modes are subtle."""

    def _stub(self, replies):
        """Return an _ask stub that yields `replies` in order, then repeats the last."""
        seq = list(replies)
        def fake(seat, instruction, context=""):
            return (seq.pop(0) if len(seq) > 1 else seq[0]), "openrouter:test"
        return fake

    def test_it_keeps_the_best_draft_not_the_last(self):
        """Measured on the first live run: 6/10 -> revised -> 4/10. Models over-correct and
        break working output while 'addressing feedback'. Shipping the final round would throw
        away a better earlier version for no reason."""
        scores = iter(["SCORE: 8\nFIXES:\n- tighten it", "SCORE: 3\nFIXES:\n- none"])
        drafts = iter(["GOOD DRAFT", "RUINED DRAFT"])

        def fake_ask(seat, instruction, context=""):
            if "reviewing another counselor" in instruction:
                return next(scores), "openrouter:test"
            return next(drafts, "RUINED DRAFT"), "openrouter:test"

        with mock.patch.object(studio, "_ask", fake_ask):
            r = studio.run("a short note", kind="write", rounds=2, quiet=True)
        body = Path(r["artifact"]).read_text(encoding="utf-8")
        self.assertIn("GOOD DRAFT", body, "the loop shipped the WORSE revision")
        self.assertNotIn("RUINED", body)
        self.assertEqual(r["score"], 8, "reported score must match what was shipped")

    def test_an_accepted_draft_stops_the_loop(self):
        """Every extra round is another billed call. 8+ must not keep revising."""
        with mock.patch.object(studio, "_ask",
                               self._stub(["SCORE: 9\nFIXES:\n- none"])):
            r = studio.run("a note", kind="write", rounds=3, quiet=True)
        self.assertEqual(len(r["rounds"]), 1, "accepted work must not be revised further")

    def test_an_unparseable_critic_does_not_deadlock(self):
        """A broken critic must not block work forever — it degrades to a pass, recorded."""
        with mock.patch.object(studio, "_ask", self._stub(["I really like it!"])):
            r = studio.run("a note", kind="write", rounds=3, quiet=True)
        self.assertTrue(r["ok"])
        self.assertEqual(r["rounds"][0]["verdict"], "critic-unparseable")

    def test_template_mode_is_labelled_not_hidden(self):
        """A $0 demo that pretends to be finished work poisons the one thing this project sells."""
        with mock.patch.object(studio, "_ask", lambda *a, **k: ("stub", "template")):
            r = studio.run("a note", kind="write", rounds=2, quiet=True)
        self.assertTrue(r["degraded"])
        self.assertIn("TEMPLATE MODE", Path(r["artifact"]).read_text(encoding="utf-8"))


class TestArtifactChecks(unittest.TestCase):
    def test_a_cli_refusing_its_arguments_is_a_PASS(self):
        """First live run generated a correct `dedupe.py <root>` and the checker marked it FAIL,
        because running it bare made argparse exit 2. Penalising that would train the studio to
        emit scripts that take no arguments — i.e. worse scripts."""
        code = ("import argparse\n"
                "p = argparse.ArgumentParser()\n"
                "p.add_argument('root')\n"
                "a = p.parse_args()\n")
        res = studio._run_python(code)
        self.assertTrue(res["ran"], f"CLI tool wrongly failed: {res}")
        self.assertEqual(res["stage"], "cli")

    def test_broken_syntax_fails(self):
        res = studio._run_python("def f(\n")
        self.assertFalse(res["ran"])
        self.assertEqual(res["stage"], "syntax")

    def test_working_script_passes(self):
        self.assertTrue(studio._run_python("print('hi')")["ran"])

    def test_html_must_be_self_contained(self):
        bad = studio._check_html('<div><script src="https://cdn.example/x.js"></script></div>')
        self.assertFalse(bad["ran"])
        self.assertIn("external URL", bad["error"])
        self.assertTrue(studio._check_html("<div><p>hello</p></div>")["ran"])


class TestCostGuard(unittest.TestCase):
    """MINDBOT_FREE must beat MINDBOT_MODEL.

    It used to be the other way round. A .env holding BOTH `MINDBOT_FREE=1` and
    `MINDBOT_MODEL=z-ai/glm-5.2` billed every single call while showing a $0 guard the operator
    believed was holding — $0.46 in one session that was supposed to be free. The failure is
    asymmetric: wrongly forcing a free model costs one run's quality; wrongly honouring a paid
    pin in an unattended loop costs money that isn't there.
    """

    def _slugs_chosen(self, env):
        seen = {}
        def fake_openai_style(url, slug, system, prompt, key):
            seen["slug"] = slug
            return "ok"
        from mindbot_pipeline import models
        # Neutralise EVERY ambient router knob, not just the two under test. The developer's
        # .env sets MINDBOT_FREE=1 and MINDBOT_MODAL=1. The first leaked in and made the
        # "no guard" case pick a free model — passing for the wrong reason. The second was
        # worse: the Modal tier short-circuits BEFORE OpenRouter, so the stub never fired, the
        # slug came back None, and the suite started making real network calls to a live GPU
        # endpoint (runtime 0.3s -> 8s).
        # A unit test that depends on the developer's .env is not a unit test.
        base = {"MINDBOT_FREE": "", "MINDBOT_MODEL": "", "MINDBOT_MODAL": "",
                "MINDBOT_NO_SONIC": "1", "OPENROUTER_API_KEY": "test-key"}
        with mock.patch.dict(os.environ, {**base, **env}, clear=False), \
             mock.patch.object(models, "_openai_style", fake_openai_style), \
             mock.patch.object(models, "free_models", lambda k: ["vendor/free-a:free"]):
            models._llm_call("openrouter", "Sage", "sys", "prompt")
        return seen.get("slug")

    def test_free_overrides_a_billable_pin(self):
        slug = self._slugs_chosen({"MINDBOT_FREE": "1", "MINDBOT_MODEL": "z-ai/glm-5.2"})
        self.assertTrue(slug.endswith(":free"), f"COST GUARD FAILED — would have billed {slug}")

    def test_a_pin_that_is_itself_free_is_honoured(self):
        """The guard exists to stop spending, not to override the operator for its own sake."""
        slug = self._slugs_chosen({"MINDBOT_FREE": "1", "MINDBOT_MODEL": "vendor/pinned:free"})
        self.assertEqual(slug, "vendor/pinned:free")

    def test_without_the_guard_the_pin_still_wins(self):
        slug = self._slugs_chosen({"MINDBOT_MODEL": "z-ai/glm-5.2"})
        self.assertEqual(slug, "z-ai/glm-5.2")


if __name__ == "__main__":
    unittest.main()

