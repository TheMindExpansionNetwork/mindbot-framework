"""
Tests for the Snake app assets.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

class TestSnakeAssets(unittest.TestCase):
    def test_index_html_contents(self):
        # Path mapping: 
        # parents[0] -> framework/tests
        # parents[1] -> framework
        # parents[2] -> repo root
        repo_root = Path(__file__).resolve().parents[2]
        index_path = repo_root / "apps" / "snake" / "index.html"
        
        self.assertTrue(index_path.exists(), f"index.html not found at {index_path}")
        
        content = index_path.read_text(encoding="utf-8")
        self.assertIn("canvas", content, "Missing 'canvas' in index.html")
        self.assertIn("DATA SERPENT", content, "Missing 'DATA SERPENT' in index.html")
        self.assertIn("5eead4", content, "Missing cyan brand hex '5eead4' in index.html")

if __name__ == "__main__":
    unittest.main()
