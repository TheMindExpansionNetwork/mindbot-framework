"""Tests for the MCP client (config + API surface; live loopback is best-effort)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mindbot_pipeline import mcp_client


class TestMCPClient(unittest.TestCase):
    def test_api_surface(self):
        for fn in ("load_config", "discover", "call_tool"):
            self.assertTrue(callable(getattr(mcp_client, fn)))
        self.assertTrue(hasattr(mcp_client, "MCPConn"))

    def test_config_loads_with_self_server(self):
        cfg = mcp_client.load_config()
        self.assertIn("servers", cfg)
        # the shipped config defines a 'self' loopback to our own MCP server
        self.assertIn("self", cfg["servers"])

    def test_discover_returns_dict(self):
        # best-effort: spawning a subprocess may be slow/unavailable in CI;
        # we only assert the shape, not specific tools (no network, no flake).
        out = mcp_client.discover(only="__none__")  # no server matches -> {}
        self.assertIsInstance(out, dict)


if __name__ == "__main__":
    unittest.main()
