"""Proof-of-Autonomy: the hash-chained ledger must VERIFY when honest and CATCH any tamper.

This is the property that's new for autonomous agents — so it gets a real adversarial test:
build a chain, then alter / insert / truncate it and prove the verifier notices every time.
"""
import importlib
import json
import tempfile
import unittest
from pathlib import Path

from mindbot_pipeline import collaboration, provenance


class TestProvenance(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._saved_path = collaboration.LEDGER_PATH
        collaboration.LEDGER_PATH = Path(self._tmp) / "ledger.jsonl"  # fresh dir → fresh .head sidecar
        # write a real chain through the (locked, hashing) ledger writer
        for i in range(5):
            collaboration.ledger("pulse", f"did thing {i}", "tester")

    def tearDown(self):
        collaboration.LEDGER_PATH = self._saved_path
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_honest_chain_verifies(self):
        v = provenance.verify()
        self.assertTrue(v["intact"])
        self.assertEqual(v["entries"], 5)
        self.assertEqual(len(v["head"]), 64)  # a real sha256

    def test_edit_is_detected(self):
        lines = collaboration.LEDGER_PATH.read_text(encoding="utf-8").splitlines()
        e = json.loads(lines[2])
        e["detail"] = "TAMPERED — never happened"      # alter content, leave the hash
        lines[2] = json.dumps(e)
        collaboration.LEDGER_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        v = provenance.verify()
        self.assertFalse(v["intact"])
        self.assertEqual(v["break_at"], 3)             # seq 3 is the 3rd entry

    def test_deletion_is_detected(self):
        lines = collaboration.LEDGER_PATH.read_text(encoding="utf-8").splitlines()
        del lines[2]                                    # remove an entry -> broken link
        collaboration.LEDGER_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertFalse(provenance.verify()["intact"])

    def test_attest_is_clean_on_honest_chain(self):
        a = provenance.attest()
        self.assertTrue(a["chain_intact"])
        self.assertTrue(a["constitution_clean"])
        self.assertEqual(a["autonomous_external_actions"], 0)
        self.assertIn("PROOF-OF-AUTONOMY", provenance.attestation_text(a))


if __name__ == "__main__":
    unittest.main()
    _ = importlib  # silence unused on some linters
