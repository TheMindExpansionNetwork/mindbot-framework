import unittest
import sys
import os

# Add framework directory to sys.path to allow importing mindbot_pipeline
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mindbot_pipeline.harness import _safe

class TestHarness(unittest.TestCase):
    def test_safe_escape(self):
        # Test for dot-dot-slash escape
        with self.assertRaises(ValueError) as cm:
            _safe("../../etc/passwd")
        self.assertIn("escapes repo", str(cm.exception))

    def test_safe_forbidden(self):
        # Test for .env forbidden path
        with self.assertRaises(ValueError) as cm:
            _safe(".env")
        self.assertIn("forbidden path", str(cm.exception))

if __name__ == "__main__":
    unittest.main()