"""SEALED — the commit-reveal that makes an LLM's hidden state checkable.

Every test here is an ATTACK. A fairness proof that only ever returns PASS is decoration, and
decoration on this particular feature would be worse than nothing: it would let someone claim
their AI opponent was provably fair when it wasn't.

The suite runs against a temporary ledger, so playing games in the test suite never pollutes
the real chain — a mistake this project has already made once with anchors.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from mindbot_pipeline import collaboration, sealed

_TMP = None
_SAVED = None


def setUpModule():
    global _TMP, _SAVED
    _TMP = Path(tempfile.mkdtemp(prefix="mindbot-sealed-"))
    _SAVED = (collaboration.COLLAB, collaboration.LEDGER_PATH, sealed.VAULT)
    collaboration.COLLAB = _TMP
    collaboration.LEDGER_PATH = _TMP / "ledger.jsonl"
    sealed.VAULT = _TMP / "sealed"
    collaboration.ledger("test_seed", "start", "test")


def tearDownModule():
    collaboration.COLLAB, collaboration.LEDGER_PATH, sealed.VAULT = _SAVED
    shutil.rmtree(_TMP, ignore_errors=True)


class TestCommitment(unittest.TestCase):
    def test_the_secret_never_reaches_the_ledger(self):
        """The whole point: publish the commitment, keep the value."""
        sealed.seal("narwhal", kind="t")
        raw = collaboration.LEDGER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("narwhal", raw, "THE SECRET WAS WRITTEN TO THE LEDGER")

    def test_commitment_is_reproducible_and_nonce_dependent(self):
        a = sealed.commitment("n1", "otter")
        self.assertEqual(a, sealed.commitment("n1", "otter"))
        self.assertNotEqual(a, sealed.commitment("n2", "otter"))

    def test_nonce_defeats_a_dictionary_attack(self):
        """Without a nonce, hashing every animal reads the word straight off the ledger."""
        r1 = sealed.seal("otter", kind="t")
        r2 = sealed.seal("otter", kind="t")
        self.assertNotEqual(r1["commitment"], r2["commitment"],
                            "same secret must not produce the same commitment twice")

    def test_empty_secret_refused(self):
        for bad in ("", "   "):
            with self.assertRaises(ValueError):
                sealed.seal(bad)


class TestHonestGame(unittest.TestCase):
    def test_an_untouched_record_passes_every_check(self):
        r = sealed.seal("toaster", kind="t")
        qs = [collaboration.ledger("q", f"question {i}", "t") or (r["seq"] + i + 1)
              for i in range(3)]
        a = sealed.audit(r["commitment"], qs)
        self.assertTrue(a["ok"], a["reasons"])
        self.assertTrue(all(a["checks"].values()))


class TestCheatDetection(unittest.TestCase):
    """The load-bearing tests. Each is a distinct way to cheat."""

    def _sealed(self, word="toaster"):
        r = sealed.seal(word, kind="t")
        return r, sealed.VAULT / f"{r['commitment'][:16]}.json"

    def test_swapping_the_word_is_caught(self):
        """The classic: claim afterwards that it was something else all along."""
        r, p = self._sealed()
        rec = json.loads(p.read_text(encoding="utf-8"))
        rec["secret"] = "kettle"
        p.write_text(json.dumps(rec), encoding="utf-8")
        a = sealed.audit(r["commitment"], [r["seq"] + 1])
        self.assertFalse(a["ok"])
        self.assertFalse(a["checks"]["hash_matches"])

    def test_swapping_the_word_AND_rehashing_is_still_caught(self):
        """The smarter forgery, and the one that nearly got through.

        Rewriting the secret and recomputing the commitment satisfies hash_matches — the file
        is internally consistent. It fails because the LEDGER still carries the original
        commitment at that seq, and a local file cannot rewrite a hash-chained entry.
        """
        r, p = self._sealed()
        rec = json.loads(p.read_text(encoding="utf-8"))
        rec["secret"] = "kettle"
        rec["nonce"] = "deadbeef" * 4
        rec["commitment"] = sealed.commitment(rec["nonce"], "kettle")
        forged = sealed.VAULT / f"{rec['commitment'][:16]}.json"
        forged.write_text(json.dumps(rec), encoding="utf-8")

        a = sealed.audit(rec["commitment"], [r["seq"] + 1])
        self.assertTrue(a["checks"]["hash_matches"], "the forgery is internally consistent")
        self.assertFalse(a["checks"]["on_the_ledger"], "THE LEDGER CROSS-CHECK FAILED TO FIRE")
        self.assertFalse(a["ok"])

    def test_committing_after_the_questions_is_caught(self):
        """Peek at the questions, then choose a word that survives them."""
        collaboration.ledger("q", "an early question", "t")
        early = json.loads((collaboration.COLLAB / "ledger.jsonl.head")
                           .read_text(encoding="utf-8"))["seq"]
        r = sealed.seal("otter", kind="t")          # sealed AFTER the question
        a = sealed.audit(r["commitment"], [early])
        self.assertFalse(a["ok"])
        self.assertFalse(a["checks"]["committed_first"])

    def test_a_record_with_no_ledger_entry_is_rejected(self):
        """A wholly invented game, never played."""
        fake = {"kind": "t", "secret": "ghost", "nonce": "ab" * 16, "seq": 999999}
        fake["commitment"] = sealed.commitment(fake["nonce"], "ghost")
        sealed.VAULT.mkdir(parents=True, exist_ok=True)
        (sealed.VAULT / f"{fake['commitment'][:16]}.json").write_text(
            json.dumps(fake), encoding="utf-8")
        a = sealed.audit(fake["commitment"], [])
        self.assertFalse(a["checks"]["on_the_ledger"])
        self.assertFalse(a["ok"])

    def test_unknown_commitment_reports_cleanly(self):
        a = sealed.audit("f" * 64, [])
        self.assertFalse(a["ok"])
        self.assertIn("no sealed record", a["problem"])


class TestScrub(unittest.TestCase):
    """The model leaks its own secret in the clarification. Measured, not hypothetical."""

    def test_the_secret_is_removed_from_a_clarification(self):
        from mindbot_pipeline.twenty import _scrub
        self.assertNotIn("giraffe", _scrub("giraffe is a mammal", "giraffe").lower())
        self.assertNotIn("giraffes", _scrub("giraffes are tall", "giraffe").lower())

    def test_multiword_secrets_are_caught_by_any_word(self):
        from mindbot_pipeline.twenty import _scrub
        out = _scrub("polar bears live on ice", "polar bear").lower()
        self.assertNotIn("bear", out)

    def test_ordinary_text_survives(self):
        from mindbot_pipeline.twenty import _scrub
        self.assertEqual(_scrub("it is often found indoors", "toaster"),
                         "it is often found indoors")


if __name__ == "__main__":
    unittest.main()
