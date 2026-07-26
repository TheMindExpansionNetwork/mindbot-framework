import unittest
import sys
import os

# Add framework to sys.path to allow imports from mindbot_pipeline
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mindbot_pipeline.familiars import fetch, FAMILIARS

class TestFamiliars(unittest.TestCase):
    def test_familiars_count(self):
        # Assert FAMILIARS has 11 entries
        self.assertEqual(len(FAMILIARS), 11, "FAMILIARS should have exactly 11 entries")

    def test_fetch_return_type(self):
        # Assert fetch returns a 2-tuple of strings
        result = fetch("Forge", "I need the board state")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], str)
        self.assertIsInstance(result[1], str)

if __name__ == '__main__':
    unittest.main()