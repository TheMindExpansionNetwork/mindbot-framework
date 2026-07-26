"""THE NOTARY — external verifiability. The tests that matter are adversarial.

The headline property: a hash chain alone CANNOT detect wholesale replacement (delete the
ledger, rebuild it, and chain verification still says INTACT). These tests prove the notary
catches exactly that attack, plus that inclusion proofs verify standalone and reject forgery.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from mindbot_pipeline import collaboration, notary, provenance


class TestNotary(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._saved = (collaboration.LEDGER_PATH, collaboration.COLLAB, notary.ANCHORS)
        collaboration.COLLAB = Path(self._tmp)
        collaboration.LEDGER_PATH = Path(self._tmp) / "ledger.jsonl"
        notary.ANCHORS = Path(self._tmp) / "ANCHORS.jsonl"
        for i in range(6):
            collaboration.ledger("pulse", f"did thing {i}", "tester")

    def tearDown(self):
        collaboration.LEDGER_PATH, collaboration.COLLAB, notary.ANCHORS = self._saved
        shutil.rmtree(self._tmp, ignore_errors=True)

    # ── merkle basics ────────────────────────────────────────────────────────
    def test_root_is_stable_and_changes_when_history_grows(self):
        r1 = notary.merkle_root()
        self.assertEqual(len(r1), 64)
        self.assertEqual(r1, notary.merkle_root())          # deterministic
        collaboration.ledger("pulse", "one more", "tester")
        self.assertNotEqual(r1, notary.merkle_root())       # commits to everything

    # ── inclusion proofs ─────────────────────────────────────────────────────
    def test_inclusion_proof_verifies_standalone(self):
        p = notary.prove(3)
        self.assertIsNotNone(p)
        self.assertTrue(notary.check_proof(p))               # verifies with no ledger access
        self.assertEqual(p["root"], notary.merkle_root())
        self.assertEqual(p["claim"]["event"], "pulse")

    def test_forged_proof_is_rejected(self):
        p = notary.prove(3)
        p["claim"]["detail"] = "something that never happened"
        p["entry_hash"] = "0" * 64                           # swap in a fake entry
        self.assertFalse(notary.check_proof(p))

    def test_every_entry_is_provable(self):
        for seq in range(1, 7):
            self.assertTrue(notary.check_proof(notary.prove(seq)), f"seq {seq} failed")

    # ── THE HEADLINE TEST ────────────────────────────────────────────────────
    def test_wholesale_replacement_is_caught_by_the_notary(self):
        """A rebuilt ledger passes chain verification but MUST fail the notary audit."""
        notary.anchor("before")                              # publish the root (git would push this)
        anchored = notary.anchors()[-1]["merkle_root"]

        # the attack: nuke history and rebuild a perfectly self-consistent fake
        collaboration.LEDGER_PATH.write_text("", encoding="utf-8")
        for i in range(6):
            collaboration.ledger("pulse", f"FAKE history {i}", "attacker")

        # 1) the chain alone is fooled — this is precisely why anchoring is required
        self.assertTrue(provenance.verify()["intact"])

        # 2) the notary is not
        a = notary.audit()
        self.assertFalse(a["all_match"])
        self.assertNotEqual(notary.merkle_root(), anchored)
        self.assertIn("MISMATCH", " ".join(c["reason"] for c in a["checks"]).upper())

    def test_truncation_is_caught(self):
        notary.anchor("full")
        lines = collaboration.LEDGER_PATH.read_text(encoding="utf-8").splitlines()
        collaboration.LEDGER_PATH.write_text("\n".join(lines[:3]) + "\n", encoding="utf-8")
        a = notary.audit()
        self.assertFalse(a["all_match"])                     # anchor is ahead of the ledger

    def test_honest_history_still_matches_its_anchors(self):
        notary.anchor("checkpoint")
        collaboration.ledger("pulse", "legit new work", "tester")   # appending is fine
        a = notary.audit()
        self.assertTrue(a["all_match"])                      # past roots still reproduce
        self.assertTrue(a["notarized"])

    # ── the attestation reflects it ──────────────────────────────────────────
    def test_attestation_separates_edited_from_replaced(self):
        att = provenance.attest()
        self.assertTrue(att["constitution_clean"])
        self.assertFalse(att["externally_verified"])         # nothing anchored yet
        notary.anchor("now")
        att = provenance.attest()
        self.assertTrue(att["externally_verified"])          # anchored + matching
        self.assertIn("EXTERNALLY VERIFIED", provenance.attestation_text(att))


if __name__ == "__main__":
    unittest.main()
    _ = json
