"""Core tests — stdlib unittest only, like everything else in the hive.

Run:  cd framework && python -m unittest discover tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mindbot_pipeline import collaboration
from mindbot_pipeline.counselors import COUNSELORS, route
from mindbot_pipeline.nucleus import verify


class TestRouting(unittest.TestCase):
    def test_domains_route_to_specialists(self):
        self.assertEqual(route("refactor the scheduler module")[0], "Forge")
        self.assertEqual(route("dream_cycle canvas batch")[0], "Spark")
        self.assertEqual(route("update the white paper section")[0], "Scribe")
        self.assertEqual(route("research open-source patterns for gig outreach")[0], "Seeker")
        self.assertEqual(route("plan the 360 scan strategy for 2045")[0], "Oracle")

    def test_unmatched_falls_back_to_sage(self):
        counselor, reason = route("zzz nothing matches this zzz")
        self.assertEqual(counselor, "Sage")
        self.assertIn("fallback", reason)

    def test_eleven_seats(self):
        self.assertEqual(len(COUNSELORS), 11)
        self.assertIn("Mind", COUNSELORS)


class TestVerifyGate(unittest.TestCase):
    def test_empty_draft_fails_loudly(self):
        ok, why = verify("")
        self.assertFalse(ok)
        self.assertIn("empty", why)

    def test_transmission_claims_are_constitution_violations(self):
        ok, why = verify("Done! I have sent the email to the venue.")
        self.assertFalse(ok)
        self.assertIn("constitution", why)

    def test_need_markers_pass_with_note(self):
        ok, why = verify("Price ladder: [NEED: floor from human]")
        self.assertTrue(ok)
        self.assertIn("NEED", why)


class TestTodoRoundTrip(unittest.TestCase):
    """claim → complete round-trip against a temp TODO file."""

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.todo = self.tmp / "BIG_TODO_LIST.md"
        self.todo.write_text(
            "# test\n- [ ] first open task\n- [x] already done\n- [ ] second open task\n",
            encoding="utf-8")
        self._orig = collaboration.TODO_PATH
        collaboration.TODO_PATH = self.todo
        self._orig_ledger = collaboration.LEDGER_PATH
        collaboration.LEDGER_PATH = self.tmp / "ledger.jsonl"

    def tearDown(self):
        collaboration.TODO_PATH = self._orig
        collaboration.LEDGER_PATH = self._orig_ledger

    def test_claim_takes_first_unclaimed(self):
        claimed = collaboration.claim_task("TestBot")
        self.assertEqual(claimed["text"], "first open task")
        text = self.todo.read_text(encoding="utf-8")
        self.assertIn("- [~] (claimed: TestBot", text)

    def test_complete_marks_done_with_note(self):
        collaboration.claim_task("TestBot")
        ok = collaboration.complete_task("TestBot", "first open task", note="tested")
        self.assertTrue(ok)
        self.assertIn("- [x] first open task", self.todo.read_text(encoding="utf-8"))

    def test_read_tasks_counts(self):
        tasks = collaboration.read_tasks()
        self.assertEqual(len(tasks), 3)
        self.assertEqual(sum(t["done"] for t in tasks), 1)

    def test_ledger_appends(self):
        collaboration.ledger("test_event", "detail line", "TestBot")
        self.assertIn("test_event", collaboration.LEDGER_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
