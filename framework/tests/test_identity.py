"""IDENTITY — the self-model must be DERIVED, and it must stay honest.

These tests exist because a self-description is the easiest thing in a codebase to let drift
into marketing. They pin two properties:
  1. capabilities/history come from real sources (live command tree, real ledger) — so the
     self-report cannot claim abilities the software does not have;
  2. the limits — including "I am not conscious" — are shipped, non-empty, and cannot be
     quietly deleted by a future edit.
"""
import unittest

from mindbot_pipeline import identity


class TestDerivedNotAsserted(unittest.TestCase):
    def test_capabilities_are_introspected_from_the_real_cli(self):
        c = identity.capabilities()
        self.assertGreater(c["command_count"], 20, "commands should be read from the live CLI")
        # commands that definitely exist must appear; a hardcoded list would drift from these
        for cmd in ("attest", "budget", "mod", "notarize", "whoami", "firm"):
            self.assertIn(cmd, c["commands"], f"'{cmd}' missing from the introspected set")

    def test_council_and_mods_are_real(self):
        c = identity.capabilities()
        self.assertEqual(len(c["counselors"]), 11)
        for m in c["mods"]:                       # every mod reports its DECLARED permissions
            self.assertIn("permissions", m)

    def test_history_comes_from_the_ledger(self):
        h = identity.history()
        self.assertGreaterEqual(h["recorded_actions"], 0)
        self.assertIsInstance(h["top_events"], list)
        # it reports what the ledger holds; it cannot invent a number
        self.assertIn("pulses", h)

    def test_standing_reflects_the_real_proof_and_budget_systems(self):
        s = identity.standing()
        for k in ("chain_intact", "autonomous_external_actions", "budget_enforced"):
            self.assertIn(k, s, f"standing must report {k}")


class TestHonesty(unittest.TestCase):
    """The load-bearing tests. If these fail, the project has started lying."""

    def test_limits_are_shipped_and_substantial(self):
        self.assertGreaterEqual(len(identity.LIMITS), 5, "limits must not be trimmed away")
        for lim in identity.LIMITS:
            self.assertGreater(len(lim), 30, "a limit must actually say something")

    def test_it_explicitly_denies_being_conscious(self):
        blob = (" ".join(identity.LIMITS) + " " + identity.whoami()["self_awareness"]).lower()
        self.assertTrue(
            ("not conscious" in blob) or ("not sentient" in blob),
            "MindBot must state plainly that it is not conscious/sentient",
        )
        self.assertIn("not", blob)

    def test_it_does_not_claim_capabilities_it_lacks(self):
        """No send/post/publish/pay path exists — the self-model must not imply one."""
        w = identity.whoami()
        text = (w["purpose"] + " " + " ".join(p["meaning"] for p in w["charter"])).lower()
        self.assertNotIn("autonomously send", text)
        self.assertNotIn("sentient", text)
        # and the charter must affirm the human gate
        joined = " ".join(p["principle"] + p["meaning"] for p in w["charter"]).lower()
        self.assertTrue("never sends" in joined or "human" in joined)

    def test_whoami_is_complete_and_serializable(self):
        import json
        w = identity.whoami()
        for k in ("name", "version", "purpose", "charter", "capabilities",
                  "history", "standing", "limits", "self_awareness"):
            self.assertIn(k, w)
        json.dumps(w)                              # must survive /api and --json


if __name__ == "__main__":
    unittest.main()
