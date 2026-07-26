"""Tests for the commons + witness ledger features (no network)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mindbot_pipeline import collaboration


class TestCommonsWitness(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "ledger.jsonl"
        self._orig = collaboration.LEDGER_PATH
        collaboration.LEDGER_PATH = self.tmp

    def tearDown(self):
        collaboration.LEDGER_PATH = self._orig

    def test_witness_writes_ledger_line(self):
        collaboration.ledger("witnessed", "Maria - first resume", "Operator")
        lines = self.tmp.read_text(encoding="utf-8").splitlines()
        e = json.loads(lines[-1])
        self.assertEqual(e["event"], "witnessed")
        self.assertIn("Maria", e["detail"])

    def test_commons_hour_fund_and_use_recorded(self):
        collaboration.ledger("commons_hour", "fund 100 rave", "Operator")
        collaboration.ledger("commons_hour", "use 12", "Operator")
        funded = used = 0
        import re
        for line in self.tmp.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            if e["event"] == "commons_hour":
                m = re.match(r"(fund|use)\s+(\d+)", e["detail"])
                if m and m.group(1) == "fund":
                    funded += int(m.group(2))
                elif m:
                    used += int(m.group(2))
        self.assertEqual(funded, 100)
        self.assertEqual(used, 12)


if __name__ == "__main__":
    unittest.main()
