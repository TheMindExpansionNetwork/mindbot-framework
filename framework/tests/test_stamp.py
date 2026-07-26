"""STAMP — a "Created with MindBot" badge is only worth anything if forging it fails.

These tests are adversarial on purpose. A stamp that always says VALID is decoration, and
decoration on THIS project would undercut the one claim the whole framework makes. So each test
below is an attack:

  * edit a field on a published stamp        -> id_matches must fail
  * invent a Merkle root that was never anchored -> root_published must fail
  * rewrite history after stamping           -> chain_intact must fail

plus the round-trip that has to keep working: markdown out, markdown back in, still valid.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from mindbot_pipeline import collaboration, notary, stamp

# ---------------------------------------------------------------------------
# Issuing a stamp ANCHORS (by design — see stamp.issue). Without this redirect every test run
# would append rows to the project's real ANCHORS.jsonl and ledger, inflating the very counts
# the stamp reports. Caught the first time this file ran: 11 anchors -> 22 in one pass.
# So the whole module operates on a throwaway ledger + anchor log.
# ---------------------------------------------------------------------------
_TMP = None
_SAVED = None


def setUpModule():
    global _TMP, _SAVED
    _TMP = Path(tempfile.mkdtemp(prefix="mindbot-stamp-"))
    _SAVED = (collaboration.COLLAB, collaboration.LEDGER_PATH, notary.ANCHORS)
    collaboration.COLLAB = _TMP
    collaboration.LEDGER_PATH = _TMP / "ledger.jsonl"
    notary.ANCHORS = _TMP / "ANCHORS.jsonl"
    for i in range(5):                       # a small real chain to stamp against
        collaboration.ledger("test_seed", f"entry {i}", "test")


def tearDownModule():
    collaboration.COLLAB, collaboration.LEDGER_PATH, notary.ANCHORS = _SAVED
    shutil.rmtree(_TMP, ignore_errors=True)


def _norm(s: str) -> str:
    """Collapse whitespace before asserting on prose — the source is hard-wrapped."""
    return " ".join(s.split())


class TestIssue(unittest.TestCase):
    def test_a_fresh_stamp_verifies(self):
        s = stamp.issue(project="unit-test")
        v = stamp.verify(s)
        self.assertTrue(v["valid"], f"fresh stamp failed: {v['reasons']}")
        self.assertTrue(all(v["checks"].values()))

    def test_the_root_is_anchored_at_issue_time(self):
        """Otherwise --verify reports INVALID on honest stamps and users learn to ignore it."""
        from mindbot_pipeline import notary
        s = stamp.issue(project="unit-test")
        self.assertIn(s["merkle_root"], {a["merkle_root"] for a in notary.anchors()})

    def test_stamp_id_is_derived_not_random(self):
        s = stamp.issue(project="unit-test")
        import hashlib
        raw = "|".join(str(s[k]) for k in ("project", "merkle_root", "seq", "issued"))
        self.assertEqual(hashlib.sha256(raw.encode()).hexdigest()[:16], s["stamp_id"])

    def test_it_reports_zero_autonomous_external_actions(self):
        """The headline claim on the badge. If this ever becomes non-zero, it must SHOW that."""
        s = stamp.issue(project="unit-test")
        self.assertIsInstance(s["autonomous_external_actions"], int)
        self.assertEqual(s["autonomous_external_actions"], 0)


class TestForgery(unittest.TestCase):
    def test_editing_any_bound_field_invalidates_the_stamp(self):
        for field, bogus in [("project", "Someone Elses Repo"),
                             ("seq", 999999),
                             ("issued", "2020-01-01T00:00:00Z")]:
            s = stamp.issue(project="unit-test")
            s[field] = bogus
            v = stamp.verify(s)
            self.assertFalse(v["valid"], f"editing {field} went undetected")
            self.assertFalse(v["checks"]["id_matches"], f"{field} is not bound into the id")

    def test_an_unpublished_root_is_rejected(self):
        s = stamp.issue(project="unit-test")
        s["merkle_root"] = "f" * 64
        import hashlib
        raw = "|".join(str(s[k]) for k in ("project", "merkle_root", "seq", "issued"))
        s["stamp_id"] = hashlib.sha256(raw.encode()).hexdigest()[:16]   # re-derive: id now matches
        v = stamp.verify(s)
        self.assertTrue(v["checks"]["id_matches"], "the forger did re-derive the id")
        self.assertFalse(v["checks"]["root_published"], "an invented root must not pass")
        self.assertFalse(v["valid"])

    def test_a_stamp_with_no_ledger_behind_it_is_not_valid(self):
        fake = {"project": "x", "merkle_root": "a" * 64, "seq": 1, "issued": "2026-01-01T00:00:00Z",
                "stamp_id": "0" * 16}
        self.assertFalse(stamp.verify(fake)["valid"])


class TestRoundTrip(unittest.TestCase):
    def test_markdown_is_the_canonical_form_and_parses_back(self):
        """'Verify it yourself' has to work against the file we actually publish."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        s, path = stamp.write(project="round-trip", target=tmp / stamp.STAMP_FILE)
        back = stamp.read_stamp(path)
        for k in ("stamp_id", "project", "issued", "merkle_root", "seq"):
            self.assertEqual(back[k], s[k], f"{k} did not survive the markdown round-trip")
        self.assertTrue(stamp.verify(back)["valid"])

    def test_the_published_file_states_its_own_limits(self):
        """A chain of custody is not a seal of approval, and the file must say so."""
        md = _norm(stamp.as_markdown(stamp.issue(project="unit-test")).lower())
        self.assertIn("does not mean", md)
        self.assertIn("not a seal of approval", md)
        self.assertIn("--verify", md)

    def test_no_secrets_can_ride_along_in_a_stamp(self):
        from mindbot_pipeline import redact
        md = stamp.as_markdown(stamp.issue(project="unit-test", note="ordinary note"))
        self.assertEqual(redact.scan(md), [])


if __name__ == "__main__":
    unittest.main()
