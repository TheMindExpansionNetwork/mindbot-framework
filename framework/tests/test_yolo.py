"""Tests for YOLO mode + auth helpers (no live network, no real model calls)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mindbot_pipeline import nucleus, models


class TestYolo(unittest.TestCase):
    def test_yolo_callable_and_evergreen(self):
        self.assertTrue(callable(nucleus.yolo))
        self.assertGreaterEqual(len(nucleus.EVERGREEN), 3)

    def test_yolo_respects_pause(self):
        flag = nucleus.PIPE_DIR / "PAUSED"
        existed = flag.exists()
        flag.write_text("test", encoding="utf-8")
        try:
            res = nucleus.yolo(max_rounds=10)
            self.assertEqual(res["rounds"], 0)  # paused immediately
        finally:
            if not existed and flag.exists():
                flag.unlink()


class TestAuth(unittest.TestCase):
    def test_validate_unknown_provider(self):
        ok, msg = models.validate_key("nope", "x")
        self.assertFalse(ok)

    def test_validate_bad_key_is_false(self):
        # a junk key must never validate true (network may fail → also false; both fine)
        ok, _ = models.validate_key("openrouter", "sk-or-DEFINITELY-INVALID-000")
        self.assertFalse(ok)

    def test_write_env_key_helper_exists(self):
        self.assertTrue(callable(models.write_env_key))


if __name__ == "__main__":
    unittest.main()
