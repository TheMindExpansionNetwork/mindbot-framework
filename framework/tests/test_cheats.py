"""The fun wing — cheat menu, oracle, trophies, rave. Cosmetic, but it shouldn't crash."""
import unittest

from mindbot_pipeline import cheats


class TestCheats(unittest.TestCase):
    def test_menu_lists_codes(self):
        m = cheats.menu_text()
        self.assertIn("konami", m)
        self.assertIn("cheat menu", m.lower())

    def test_apply_known_alias_and_unknown(self):
        self.assertIn("konami", cheats.apply("konami"))
        self.assertIn("konami", cheats.apply("uuddlrlrba"))        # the classic alias
        self.assertIn("not a code", cheats.apply("zzzz").lower())  # graceful wink

    def test_oracle_is_deterministic(self):
        # same question -> same answer (no RNG: resume-safe + testable)
        self.assertEqual(cheats.oracle("ship it?"), cheats.oracle("ship it?"))
        self.assertIn("ship it?", cheats.oracle("ship it?"))

    def test_rave_frame_is_a_string(self):
        self.assertIsInstance(cheats.rave_frame(0), str)
        self.assertTrue(cheats.rave_frame(7))

    def test_trophies_read_real_progress(self):
        rows = cheats.trophies()
        self.assertTrue(rows)
        for name, unlocked, hint in rows:
            self.assertIsInstance(unlocked, bool)
        self.assertIn("TROPHY", cheats.trophies_text())


if __name__ == "__main__":
    unittest.main()
