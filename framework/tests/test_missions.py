import sys
import unittest
import json
from pathlib import Path

# Ensure framework is in path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

class TestMissions(unittest.TestCase):
    def test_missions_json_structure(self):
        # Locate the repo-root collaboration/missions.json
        # framework/tests/test_missions.py -> parents[0]: framework/tests, parents[1]: framework, parents[2]: repo-root
        repo_root = Path(__file__).resolve().parents[2]
        missions_path = repo_root / "collaboration" / "missions.json"

        # Assert the file exists
        self.assertTrue(missions_path.exists(), f"missions.json not found at {missions_path}")

        # Load as JSON
        with open(missions_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Assert it has a 'missions' key
        self.assertIn("missions", data, "JSON missing 'missions' key")

        # Assert 'missions' is a non-empty list
        missions = data["missions"]
        self.assertIsInstance(missions, list, "'missions' should be a list")
        self.assertGreater(len(missions), 0, "'missions' list should not be empty")

        # Assert each mission has id, name, goal, and tag keys
        required_keys = {"id", "name", "goal", "tag"}
        for i, mission in enumerate(missions):
            self.assertIsInstance(mission, dict, f"Mission at index {i} is not a dictionary")
            for key in required_keys:
                self.assertIn(key, mission, f"Mission at index {i} is missing required key: {key}")

if __name__ == "__main__":
    unittest.main()