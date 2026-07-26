"""MCP CLIENT — the hive CONSUMES external MCP servers (the other half of MCP).

We already SERVE MCP (mcp_server.py). This is the reverse: connect OUT to other
people's MCP servers — filesystem, search, git, anything — list their tools, and
call them. That turns every MCP server in the world into a tool a counselor can use.

stdlib only: spawns a server as a subprocess and speaks newline-delimited JSON-RPC
2.0 over its stdio (matches our server + most lightweight MCP stdio servers). Real
LSP-style Content-Length framing is a documented TODO for heavier servers.

Config: framework/mcp_servers.json
  { "servers": { "name": { "command": "python", "args": ["-m","..."], "enabled": true } } }

CLI:  mindbot mcp-tools                 list tools from every enabled server
      mindbot mcp-call <server> <tool> '<json-args>'   call one tool

LEARNING NOTE: an MCP client is just (1) start the server process, (2) JSON-RPC
`initialize`, (3) `tools/list`, (4) `tools/call`. That's the whole protocol surface.

Extend: register a new external server -> add an entry under "servers" in
mcp_servers.json (no code change needed; discover()/call_tool() read it live).
Add a CLI command -> add a subparser + an elif in cli.main() that calls discover()
or call_tool(). To support Content-Length-framed servers, extend MCPConn._rpc.
"""

import json
import subprocess
import time

from .collaboration import PIPE_DIR, ROOT, ledger

CONFIG = PIPE_DIR / "mcp_servers.json"


def load_config():
    if not CONFIG.exists():
        return {"servers": {}}
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"servers": {}}


class MCPConn:
    """One live connection to an MCP server subprocess."""

    def __init__(self, name, command, args):
        self.name = name
        self._id = 0
        # cwd = framework/ so the loopback `python -m mindbot_pipeline.cli mcp` resolves;
        # external servers that operate on a path take it via args, not cwd.
        self.proc = subprocess.Popen(
            [command, *args], cwd=str(PIPE_DIR), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1)

    def _rpc(self, method, params=None, notify=False):
        self._id += 1
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notify:
            msg["id"] = self._id
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        if notify:
            return None
        # Correlate by id: skip blank lines and any non-JSON the server prints
        # (banners, stray logs) until we see the response whose id matches ours.
        deadline = time.time() + 30
        while time.time() < deadline:
            line = self.proc.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                resp = json.loads(line)
            except json.JSONDecodeError:
                continue
            if resp.get("id") == self._id:
                return resp
        return {"error": {"message": "timeout/no response"}}

    def initialize(self):
        r = self._rpc("initialize", {"protocolVersion": "2024-11-05",
                                     "capabilities": {}, "clientInfo": {"name": "mindbotz", "version": "1"}})
        # Protocol requires this follow-up notification before any tools/* call.
        self._rpc("notifications/initialized", notify=True)
        return r.get("result", r)

    def list_tools(self):
        r = self._rpc("tools/list")
        return (r.get("result") or {}).get("tools", [])

    def call(self, tool, args):
        r = self._rpc("tools/call", {"name": tool, "arguments": args or {}})
        return r.get("result", r)

    def close(self):
        try:
            self.proc.terminate()
        except Exception:  # noqa: BLE001
            pass


def discover(only=None):
    """Connect to every enabled server; return {server: [tool dicts]}."""
    out = {}
    for name, cfg in load_config().get("servers", {}).items():
        if not cfg.get("enabled", False) or (only and name != only):
            continue
        try:
            c = MCPConn(name, cfg["command"], cfg.get("args", []))
            c.initialize()
            out[name] = c.list_tools()
            c.close()
            ledger("mcp_discover", f"{name}: {len(out[name])} tools", "mcp-client")
        except Exception as e:  # noqa: BLE001
            out[name] = [{"error": str(e)}]
    return out


def call_tool(server, tool, args):
    cfg = load_config().get("servers", {}).get(server)
    if not cfg:
        return {"error": f"no server '{server}' in mcp_servers.json"}
    c = MCPConn(server, cfg["command"], cfg.get("args", []))
    try:
        c.initialize()
        res = c.call(tool, args)
        ledger("mcp_call", f"{server}.{tool}", "mcp-client")
        return res
    finally:
        c.close()
