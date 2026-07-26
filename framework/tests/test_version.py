import sys
import unittest
from pathlib import Path

# Ensure the framework directory is in the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mindbot_pipeline.version_info import get_version

class TestVersion(unittest.TestCase):
    def test_get_version_returns_non_empty_string(self):
        """Assert that get_version() returns a non-empty string."""
        version = get_version()
        self.assertIsInstance(version, str)
        self.assertTrue(len(version) > 0, "Version string should not be empty")

if __name__ == "__main__":
    unittest.main()