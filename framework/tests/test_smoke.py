"""Smoke tests — the cheap safety net. If something won't even import, fail loud.

This is the judge the autonomous build loop leans on: a coding agent can't ship a change
that breaks an import, because this goes red and the harness reverts it.
"""
import importlib
import pkgutil
import unittest

import mindbot_pipeline


class TestSmoke(unittest.TestCase):
    def test_every_module_imports(self):
        """Import every submodule of mindbot_pipeline without error."""
        failed = []
        for mod in pkgutil.iter_modules(mindbot_pipeline.__path__):
            name = f"mindbot_pipeline.{mod.name}"
            try:
                importlib.import_module(name)
            except Exception as e:  # noqa: BLE001
                failed.append(f"{name}: {type(e).__name__}: {e}")
        self.assertEqual(failed, [], "modules failed to import:\n  " + "\n  ".join(failed))

    def test_fleet_registry_has_three_pods(self):
        from mindbot_pipeline import fleet
        self.assertGreaterEqual(len(fleet.FLEET), 3)

    def test_counselors_are_lenses(self):
        # the council is a team of lenses; every seat has a voice + domain
        from mindbot_pipeline.counselors import COUNSELORS
        self.assertEqual(len(COUNSELORS), 11)
        for name, c in COUNSELORS.items():
            self.assertIn("domain", c, f"{name} missing domain")


if __name__ == "__main__":
    unittest.main()
