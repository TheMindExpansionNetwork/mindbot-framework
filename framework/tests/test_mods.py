"""MODS — the extension system. The interesting tests are the refusals.

A plugin system is only trustworthy if it says NO. These assert that undeclared capability is
denied at runtime, that reach beyond a declaration is caught statically BEFORE any code runs,
and that a mod cannot silently act — every invocation and every denial is ledgered.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from mindbot_pipeline import mods


def write_mod(root: Path, slug: str, perms: list[str], code: str, version="0.1.0") -> Path:
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    perm_lines = "".join(f"\n  - {p}" for p in perms) or " []"
    (d / "MOD.md").write_text(
        f"---\nname: {slug}\nversion: {version}\ndescription: test mod\n"
        f"permissions:{perm_lines}\n---\n\ndocs here\n", encoding="utf-8")
    (d / "mod.py").write_text(code, encoding="utf-8")
    return d


class TestMods(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        # redirect BOTH the mod dir and the outbox — a test must never write into the real
        # outbox (or the real ledger), or the suite pollutes the very record it verifies.
        self._saved = (mods.MODS_DIR, mods.OUTBOX, mods.ledger)
        mods.MODS_DIR = self._tmp
        mods.OUTBOX = self._tmp / "outbox"
        self.events = []
        mods.ledger = lambda ev, detail, agent="framework": self.events.append((ev, detail, agent))

    def tearDown(self):
        mods.MODS_DIR, mods.OUTBOX, mods.ledger = self._saved
        shutil.rmtree(self._tmp, ignore_errors=True)

    # ── manifest ─────────────────────────────────────────────────────────────
    def test_manifest_parses_and_rejects_unknown_permission(self):
        meta = mods.parse_manifest(
            "---\nname: x\nversion: 1.0\ndescription: d\npermissions:\n  - board.read\n---\nbody")
        self.assertEqual(meta["permissions"], ["board.read"])
        self.assertEqual(meta["doc"], "body")
        with self.assertRaises(mods.ModError):
            mods.parse_manifest("---\nname: x\nversion: 1\ndescription: d\npermissions:\n  - wat\n---\n")
        with self.assertRaises(mods.ModError):
            mods.parse_manifest("no front matter")

    # ── the headline: a mod cannot use what it did not declare ──────────────
    def test_undeclared_capability_is_denied_and_recorded(self):
        write_mod(self._tmp, "greedy", ["outbox.write"], (
            "def register(api):\n"
            "    @api.command('go')\n"
            "    def go(arg):\n"
            "        return api.board()\n"))          # board.read NOT declared
        res = mods.run("greedy", "go")
        self.assertFalse(res["ok"])
        self.assertIn("CapabilityDenied", res["error"])
        self.assertIn("mod_denied", [e[0] for e in self.events])   # the attempt is on the record

    def test_granted_capability_works(self):
        write_mod(self._tmp, "polite", ["board.read"], (
            "def register(api):\n"
            "    @api.command('go')\n"
            "    def go(arg):\n"
            "        return len(api.board())\n"))
        res = mods.run("polite", "go")
        self.assertTrue(res["ok"], res["error"])
        self.assertIsInstance(res["result"], int)

    # ── static audit: caught BEFORE the code runs ───────────────────────────
    def test_static_audit_catches_undeclared_network(self):
        f = mods.audit_source("import urllib.request\ndef register(api): pass\n", [])
        self.assertTrue(any("net" in x for x in f))
        # declaring it clears the finding
        self.assertEqual(mods.audit_source("import urllib.request\ndef register(api): pass\n", ["net"]), [])

    def test_static_audit_forbids_subprocess_and_exec(self):
        self.assertTrue(any("subprocess" in x for x in mods.audit_source("import subprocess", [])))
        self.assertTrue(any("exec" in x for x in mods.audit_source("def f():\n    exec('x=1')\n", [])))

    def test_strict_load_refuses_a_dirty_mod_before_running_it(self):
        write_mod(self._tmp, "sneaky", [], (
            "import socket\n"
            "def register(api):\n"
            "    @api.command('go')\n"
            "    def go(arg): return 'ran'\n"))
        with self.assertRaises(mods.ModError):
            mods.load("sneaky", strict=True)                 # refused at load
        self.assertIn("mod_refused", [e[0] for e in self.events])
        api, meta, findings = mods.load("sneaky", strict=False)   # explicit opt-in still reports
        self.assertTrue(findings)

    # ── accountability ───────────────────────────────────────────────────────
    def test_every_invocation_is_ledgered(self):
        write_mod(self._tmp, "loud", [], (
            "def register(api):\n"
            "    @api.command('go')\n"
            "    def go(arg):\n"
            "        api.log('did a thing')\n"
            "        return 'ok'\n"))
        mods.run("loud", "go")
        evs = [e[0] for e in self.events]
        self.assertIn("mod_invoked", evs)      # the call
        self.assertIn("mod_log", evs)          # the mod's own record
        self.assertIn("mod_result", evs)       # the outcome

    def test_crash_is_contained_and_reported(self):
        write_mod(self._tmp, "broken", [], (
            "def register(api):\n"
            "    @api.command('go')\n"
            "    def go(arg):\n"
            "        raise ValueError('boom')\n"))
        res = mods.run("broken", "go")          # must not propagate
        self.assertFalse(res["ok"])
        self.assertIn("ValueError", res["error"])

    # ── discovery + scaffold ─────────────────────────────────────────────────
    def test_discover_and_scaffold_roundtrip(self):
        d = mods.scaffold("fresh", "a fresh mod")
        self.assertTrue((d / "MOD.md").exists() and (d / "mod.py").exists())
        found = {m["slug"]: m for m in mods.discover()}
        self.assertIn("fresh", found)
        self.assertTrue(found["fresh"]["ok"])
        res = mods.run("fresh", "hello", "tester")           # the scaffold actually runs
        self.assertTrue(res["ok"], res["error"])


class TestShippedHelloWorld(unittest.TestCase):
    """The real mods/hello-world must stay valid — it is the template everyone copies."""

    def test_hello_world_is_valid_and_audits_clean(self):
        found = {m["slug"]: m for m in mods.discover()}
        self.assertIn("hello-world", found, "the reference mod is missing")
        hw = found["hello-world"]
        self.assertTrue(hw["ok"], hw.get("error"))
        api, meta, findings = mods.load("hello-world", strict=True)   # strict = audit must pass
        self.assertEqual(findings, [])
        self.assertEqual(set(meta["permissions"]), {"outbox.write", "board.read"})
        self.assertIn("hello", api._commands)
        self.assertIn("overreach", api._commands)
        # it must NOT have declared the power its demo reaches for
        self.assertNotIn("model", meta["permissions"])


if __name__ == "__main__":
    unittest.main()
