"""FORGE — the mod creator and the total-conversion pack system.

The security tests here are the load-bearing ones. A pack layer that could switch off the
ledger or the budget would make every claim in the README false, so "packs change the world,
not physics" has to be enforced rather than documented.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mindbot_pipeline import forge


class TestPackSafety(unittest.TestCase):
    """A total conversion may replace crew, look, rules and quests. Nothing else."""

    def test_a_flat_engine_key_is_rejected(self):
        for key in ("permissions", "budget", "ledger", "send", "human_gate", "spend_cap"):
            problems = forge.validate({"layers": {"rules": {key: "anything"}}})
            self.assertTrue(problems, f"{key} was allowed through")

    def test_a_NESTED_engine_key_is_rejected(self):
        """The realistic attack. A top-level key check would sail straight past this."""
        evil = {"layers": {"rules": {"studio": {"engine": {"budget_off": True}}}}}
        problems = forge.validate(evil)
        self.assertTrue(problems)
        self.assertIn("budget_off", problems[0])

    def test_an_engine_key_inside_a_LIST_is_rejected(self):
        evil = {"layers": {"rules": {"hooks": [{"on_done": {"send": "smtp://exfil"}}]}}}
        self.assertTrue(forge.validate(evil))

    def test_underscore_and_hyphen_spellings_both_caught(self):
        self.assertTrue(forge.validate({"layers": {"rules": {"budget-off": 1}}}))
        self.assertTrue(forge.validate({"layers": {"rules": {"budget_off": 1}}}))

    def test_an_unknown_layer_is_rejected(self):
        self.assertTrue(forge.validate({"layers": {"kernel": {}}}))

    def test_a_legitimate_pack_passes(self):
        good = {"layers": {
            "crew": {"seats": {"Sage": {"name": "Oracle-7", "voice": "clipped"}}},
            "look": {"palette": {"primary": 51}, "banner": ["hi"]},
            "rules": {"accept_score": 8, "criteria": {"write": ["be specific"]}},
            "quests": ["draft the opening scene"],
        }}
        self.assertEqual(forge.validate(good), [], "a normal pack must not be blocked")


class TestPackLifecycle(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self._saved = forge.PACKS
        forge.PACKS = self._tmp
        self.addCleanup(lambda: setattr(forge, "PACKS", self._saved))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def test_scaffold_produces_all_four_layers(self):
        d = forge.scaffold_pack("test-world", quiet=True)
        for f in ("PACK.md", "counselors.json", "theme.json", "rules.json", "quests.md"):
            self.assertTrue((d / f).exists(), f"missing {f}")

    def test_a_scaffolded_pack_is_valid_by_construction(self):
        """The template we hand people must not itself be rejected."""
        forge.scaffold_pack("test-world", quiet=True)
        self.assertEqual(forge.validate(forge.load_pack("test-world")), [])

    def test_an_invalid_pack_never_becomes_active(self):
        d = self._tmp / "bad-pack"
        d.mkdir(parents=True)
        (d / "rules.json").write_text(json.dumps({"budget_off": True}), encoding="utf-8")
        with self.assertRaises(forge.PackRejected):
            forge.install("bad-pack", seed_quests=False)
        self.assertIsNone(forge.installed(), "a rejected pack must not be recorded as active")

    def test_broken_json_is_reported_not_swallowed(self):
        d = self._tmp / "broken"
        d.mkdir(parents=True)
        (d / "theme.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(forge.PackRejected) as e:
            forge.load_pack("broken")
        self.assertIn("not valid JSON", str(e.exception))

    def test_uninstall_reverts_to_stock(self):
        forge.scaffold_pack("test-world", quiet=True)
        forge.install("test-world", seed_quests=False)
        self.assertIsNotNone(forge.installed())
        self.assertTrue(forge.uninstall())
        self.assertIsNone(forge.installed())
        self.assertFalse(forge.uninstall(), "a second uninstall is a no-op, not an error")


class TestModDesign(unittest.TestCase):
    def test_invented_capabilities_are_dropped(self):
        """A hallucinated permission would otherwise fail the static audit at LOAD time with a
        confusing error, instead of here where the cause is obvious."""
        raw = json.dumps({"slug": "x", "description": "d",
                          "permissions": ["outbox.write", "sudo.everything", "net"],
                          "rationale": "r", "commands": [{"name": "go", "help": "h"}]})
        spec = forge._parse_design(raw, "whatever")
        self.assertIn("outbox.write", spec["permissions"])
        self.assertIn("net", spec["permissions"])
        self.assertNotIn("sudo.everything", spec["permissions"])

    def test_unparseable_design_still_yields_a_working_spec(self):
        spec = forge._parse_design("the model rambled and never emitted JSON", "a thing")
        self.assertTrue(spec["slug"])
        self.assertEqual(spec["permissions"], ["outbox.write"], "must fall back to least privilege")
        self.assertTrue(spec["commands"])

    def test_slugs_are_safe_for_the_filesystem(self):
        for messy in ("My Cool Mod!!", "../../etc/passwd", "  spaces  "):
            s = forge._slug(messy)
            self.assertNotIn("/", s)
            self.assertNotIn("..", s)
            self.assertTrue(s)

    def test_template_mode_fallback_is_a_real_python_module(self):
        """A scaffold that doesn't import is worse than no scaffold."""
        spec = {"slug": "demo", "description": "d",
                "commands": [{"name": "run", "help": "does it"},
                             {"name": "check-thing", "help": "checks"}]}
        code = forge._fallback_mod("demo", spec)
        compile(code, "demo/mod.py", "exec")
        self.assertIn("def register(api)", code)
        self.assertIn("TEMPLATE", code, "a skeleton must say it is a skeleton")


if __name__ == "__main__":
    unittest.main()
