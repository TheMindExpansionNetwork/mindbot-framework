import sys
import unittest
from pathlib import Path

# Add framework root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mindbot_pipeline.cli import cmd_employees

class TestEmployees(unittest.TestCase):
    def test_cmd_employees_is_callable(self):
        """Verify the employees CLI command is a callable function."""
        self.assertTrue(callable(cmd_employees), "cmd_employees should be callable")

    def test_lore_files_exist(self):
        """Verify that the root lore directory contains the specific employee files."""
        # Path(__file__) is framework/tests/test_employees.py
        # parents[0]: framework/tests
        # parents[1]: framework
        # parents[2]: MINDBOTZ (root)
        root = Path(__file__).resolve().parents[2]
        lore_dir = root / "lore"
        
        self.assertTrue(lore_dir.is_dir(), f"Lore directory not found at {lore_dir}")
        
        expected_files = ["J1MSKY.md", "D0Z3R.md"]
        for filename in expected_files:
            file_path = lore_dir / filename
            self.assertTrue(file_path.exists(), f"Required lore file {filename} missing from {lore_dir}")

if __name__ == "__main__":
    unittest.main()