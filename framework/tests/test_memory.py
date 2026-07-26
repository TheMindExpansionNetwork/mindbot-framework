"""Tests for the local semantic memory index."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mindbot_pipeline import memory


class TestMemory(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "memory.jsonl"
        self._orig = memory.MEM
        memory.MEM = self.tmp

    def tearDown(self):
        memory.MEM = self._orig

    def test_store_and_search_ranks_relevant_first(self):
        memory.store("the eclipse festival happens in 2045 under the moon")
        memory.store("DJ Nexus mixes house music by Camelot wheel math")
        memory.store("the coding harness runs tests and reverts on red")
        hits = memory.search("when is the festival", k=3)
        self.assertTrue(hits)
        self.assertIn("2045", hits[0]["text"])

    def test_empty_query_returns_empty(self):
        memory.store("anything")
        self.assertEqual(memory.search("", k=3), [])

    def test_no_store_returns_empty(self):
        self.assertEqual(memory.search("anything", k=3), [])


if __name__ == "__main__":
    unittest.main()
