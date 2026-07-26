"""Tests for the autonomous loop + meeting wiring (no live model calls)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mindbot_pipeline import nucleus


class TestAutoloop(unittest.TestCase):
    def test_autoloop_callable_and_signature(self):
        self.assertTrue(callable(nucleus.autoloop))
        self.assertTrue(callable(nucleus.meeting))

    def test_autoloop_respects_pause_flag(self):
        flag = nucleus.PIPE_DIR / "PAUSED"
        existed = flag.exists()
        flag.write_text("test", encoding="utf-8")
        try:
            res = nucleus.autoloop(rounds=5)
            # paused immediately → zero pulses
            self.assertEqual(res["pulses"], 0)
        finally:
            if not existed and flag.exists():
                flag.unlink()


if __name__ == "__main__":
    unittest.main()
