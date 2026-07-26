"""REDACT — secrets must never reach an immutable, published record.

mindbot:allow-secrets — this file deliberately contains key-SHAPED test fixtures (all fake).
Without this pragma `mindbot scan` reports its own test data, and a scanner you have to ignore
stops being a scanner.


The ledger is append-only, hash-chained, and its Merkle roots are anchored publicly. A secret
written into it cannot be deleted (later `prev` hashes depend on it), edited (verify() would
report tampering), or rewritten (anchors would stop matching). Prevention is the only option,
so these tests guard the write path itself.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from mindbot_pipeline import collaboration, redact


class TestScrub(unittest.TestCase):
    def test_catches_real_provider_key_shapes(self):
        cases = {
            # NEVER paste a real key here, even to test the detector. This line originally
            # held a live OpenRouter key; it survived into git history, where it cannot be
            # deleted, and became a blocker for open-sourcing the repo. Fixtures are synthetic.
            "openrouter":  "key is sk-or-v1-0123456789abcdef0123456789abcdef0123456789ab",
            "anthropic":   "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789",
            "xai":         "xai-abcdefghijklmnopqrstuvwxyz012345",
            "google":      "AIzaSyA1234567890abcdefghijklmnopqrstuv",
            "stripe":      "sk_live_abcdefghijklmnop1234567890",
            "github":      "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
            "aws":         "AKIAIOSFODNN7EXAMPLE",
            "huggingface": "hf_abcdefghijklmnopqrstuvwxyz0123456789",
        }
        for label, text in cases.items():
            clean, found = redact.scrub(text)
            self.assertIn(label, found, f"{label} not detected")
            self.assertNotIn(text.split()[-1], clean, f"{label} survived scrubbing")

    def test_masks_password_but_keeps_the_useful_context(self):
        clean, found = redact.scrub("db at postgres://admin:hunter2secret@10.0.0.5/prod")
        self.assertIn("conn-string", found)
        self.assertNotIn("hunter2secret", clean)
        self.assertIn("postgres://admin", clean)      # entry stays diagnostically useful

    def test_named_secret_keeps_the_key_name(self):
        clean, found = redact.scrub("OPENROUTER_API_KEY=abcd1234efgh5678")
        self.assertIn("named-secret", found)
        self.assertNotIn("abcd1234efgh5678", clean)
        self.assertIn("OPENROUTER_API_KEY", clean)    # WHICH secret leaked is the signal

    def test_pem_block_is_removed_entirely(self):
        pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKC\nAQEA\n-----END RSA PRIVATE KEY-----"
        clean, found = redact.scrub(f"oops {pem} oops")
        self.assertIn("pem", found)
        self.assertNotIn("MIIEowIBAAKC", clean)

    def test_does_not_flag_our_own_hashes(self):
        """The ledger is FULL of sha256 digests and git SHAs. Flagging them would be useless."""
        noise = ("merkle root 2970b3134714d403ff104b8528071b61bb4efa87f2a137a90e1d941994a9513b "
                 "commit a8f05ec seq 224 model anthropic/claude-opus-5 cost $0.0035")
        self.assertEqual(redact.scan(noise), [], f"false positive: {redact.scan(noise)}")

    def test_ordinary_text_is_untouched(self):
        for s in ("pulse Sage: wrote a draft", "budget_denied run $0.01 > cap", "", "hello"):
            self.assertEqual(redact.scrub(s)[0], s)

    def test_no_false_positives_on_real_repo_code(self):
        """A scanner that cries wolf gets muted, which is worse than no scanner.

        Every line below is REAL code/docs from this repo that a naive name-based rule flags.
        Measured: the naive version reported 22 hits across the tree, all of them wrong.
        """
        for s in [
            "max_tokens=200",                                   # a number, not a credential
            "model, tokenizer=tok,",                            # an identifier
            "_TOKEN = re.compile(r'[a-z0-9]+')",                # a regex
            'secrets=[modal.Secret.from_name("mindbot")]',      # a function call
            "OPENROUTER_API_KEY=sk-or-v1-...",                  # .env.example placeholder
            "# STRIPE_API_KEY=sk_live_xxxxxxxx",                # docs placeholder
            "auth_method: pkce",
            "password_field: pw",
        ]:
            self.assertEqual(redact.scan(s), [], f"FALSE POSITIVE on: {s}")

    def test_still_catches_real_named_secrets(self):
        for s in ['api_key = "A1b2C3d4E5f6G7h8J9k0"', "password=Tr0ub4dor3xKcdLong"]:
            self.assertTrue(redact.scan(s), f"MISSED a real secret: {s}")


class TestAllowlistPragmas(unittest.TestCase):
    """Fixtures and docs legitimately contain key-shaped strings; without an escape hatch the
    scanner flags itself and gets muted. But the pragma must be OPT-IN, never implicit."""

    def _tmpfile(self, body: str):
        d = Path(tempfile.mkdtemp())
        f = d / "sample.py"
        f.write_text(body, encoding="utf-8")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return f

    def test_file_level_pragma_skips_the_file(self):
        key = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        self.assertTrue(redact.scan_paths([self._tmpfile(f"TOKEN='{key}'\n")]))     # flagged
        f = self._tmpfile(f"# {redact.ALLOW_FILE}\nTOKEN='{key}'\n")
        self.assertEqual(redact.scan_paths([f]), [])                                # skipped

    def test_line_level_pragma_skips_only_that_line(self):
        key = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        f = self._tmpfile(f"A='{key}'  # {redact.ALLOW_LINE}\nB='{key}'\n")
        hits = redact.scan_paths([f])
        self.assertEqual(len(hits), 1, "only the un-pragma'd line should be flagged")
        self.assertEqual(hits[0]["line"], 2)

    def test_pragma_is_not_implicit(self):
        """A file merely mentioning 'secret' must NOT be skipped."""
        key = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        f = self._tmpfile(f"# handling a secret here\nTOKEN='{key}'\n")
        self.assertTrue(redact.scan_paths([f]))


class TestLedgerWritePath(unittest.TestCase):
    """The guarantee that matters: a secret cannot get INTO the chain."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self._saved = (collaboration.LEDGER_PATH, collaboration.COLLAB)
        collaboration.COLLAB = self._tmp
        collaboration.LEDGER_PATH = self._tmp / "ledger.jsonl"

    def tearDown(self):
        collaboration.LEDGER_PATH, collaboration.COLLAB = self._saved
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_a_leaked_key_never_lands_in_the_ledger(self):
        secret = "sk-or-v1-0123456789abcdef0123456789abcdef0123456789abcdef0123456789ab"
        collaboration.ledger("mod_log", f"calling with {secret}", "mod:careless")
        raw = collaboration.LEDGER_PATH.read_text(encoding="utf-8")
        self.assertNotIn(secret, raw, "A SECRET WAS WRITTEN TO THE IMMUTABLE LEDGER")
        self.assertIn("[REDACTED:openrouter]", raw)
        self.assertIn("ledger scrubbed", raw)         # the redaction is itself disclosed

    def test_scrubbed_entry_still_hashes_and_chains_correctly(self):
        collaboration.ledger("a", "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123", "t")
        collaboration.ledger("b", "ordinary follow-up", "t")
        from mindbot_pipeline import provenance
        saved = provenance.collaboration.LEDGER_PATH
        provenance.collaboration.LEDGER_PATH = collaboration.LEDGER_PATH
        try:
            v = provenance.verify()
            self.assertTrue(v["intact"], "scrubbing broke the chain")
            self.assertEqual(v["entries"], 2)
        finally:
            provenance.collaboration.LEDGER_PATH = saved


class TestRepoScan(unittest.TestCase):
    def test_scan_paths_finds_and_masks(self):
        tmp = Path(tempfile.mkdtemp())
        f = tmp / "leaky.py"
        f.write_text("TOKEN = 'ghp_abcdefghijklmnopqrstuvwxyz0123456789'\nx = 1\n", encoding="utf-8")
        hits = redact.scan_paths([f])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["line"], 1)
        self.assertNotIn("ghp_abcdefghijklmnopqrstuvwxyz0123456789", hits[0]["preview"])
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
