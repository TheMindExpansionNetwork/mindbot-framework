"""Tests for the fleet registry + status pinger (stdlib only, no network needed)."""
import os
import unittest

from mindbot_pipeline import fleet


class TestFleet(unittest.TestCase):
    def test_registry_shape(self):
        # every pod declares the fields the CLI + OS rely on
        for cs, cfg in fleet.FLEET.items():
            for k in ("env", "model", "kind", "gpu", "desc"):
                self.assertIn(k, cfg, f"{cs} missing {k}")

    def test_url_for_unset(self):
        # an unset pod env yields empty string, not a crash
        os.environ.pop("MINDBOT_CODER_URL", None)
        self.assertEqual(fleet.url_for("c0d3r"), "")

    def test_url_for_set(self):
        os.environ["MINDBOT_CODER_URL"] = "https://example.test/v1"
        self.assertEqual(fleet.url_for("c0d3r"), "https://example.test/v1")
        os.environ.pop("MINDBOT_CODER_URL", None)

    def test_status_structure_no_network(self):
        # with no URLs set, status returns one row per pod, all 'unset', no probing/hang
        for cfg in fleet.FLEET.values():
            os.environ.pop(cfg["env"], None)
        rows = fleet.status(probe=False)
        self.assertEqual(len(rows), len(fleet.FLEET))
        for r in rows:
            self.assertEqual(r["state"], "unset")
            self.assertIn("callsign", r)


if __name__ == "__main__":
    unittest.main()
