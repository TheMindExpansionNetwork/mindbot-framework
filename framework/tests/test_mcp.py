"""Tests for the MCP server — pure dispatch, no stdio needed."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mindbot_pipeline import mcp_server as mcp


class TestMCP(unittest.TestCase):
    def test_initialize(self):
        r = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(r["result"]["serverInfo"]["name"], "mindbotz")
        self.assertIn("protocolVersion", r["result"])

    def test_tools_list_has_propose(self):
        r = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [t["name"] for t in r["result"]["tools"]]
        self.assertIn("mindbotz_propose", names)
        self.assertIn("mindbotz_board", names)

    def test_council_call_returns_text(self):
        r = mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                        "params": {"name": "mindbotz_council", "arguments": {}}})
        txt = r["result"]["content"][0]["text"]
        self.assertIn("Mind", txt)

    def test_route_call(self):
        r = mcp.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                        "params": {"name": "mindbotz_route", "arguments": {"task": "refactor the module"}}})
        self.assertIn("Forge", r["result"]["content"][0]["text"])

    def test_notification_returns_none(self):
        self.assertIsNone(mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_unknown_method_errors(self):
        r = mcp.handle({"jsonrpc": "2.0", "id": 9, "method": "bogus/thing"})
        self.assertIn("error", r)


if __name__ == "__main__":
    unittest.main()
