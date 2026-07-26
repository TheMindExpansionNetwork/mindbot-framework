"""MCP SERVER — expose the hive to any MCP client (Claude Desktop, Cursor, Hermes…).

Model Context Protocol over stdio, JSON-RPC 2.0, **stdlib only** (the 2045 rule).
This is the framework's front door for the whole agent ecosystem: any MCP-speaking
app (Hermes, Claude Desktop, Cursor, a swarm…) can READ the council's state, PROPOSE
work, and drive the storefront — but the constitution still holds. The only write
tools are `mindbotz_propose` (appends a [PROPOSED] task) and `mindbotz_sell` (drafts a
listing + a Stripe TEST-mode payment link). Neither transmits or charges — a human
Operator approves everything. The hive proposes; the operator disposes — even over MCP.

Run:  python -m mindbot_pipeline.cli mcp        (speaks newline-delimited JSON-RPC)
Wire into an MCP client's config as a stdio server pointing at that command.

handle(req) is pure (dict→dict) so it unit-tests without any stdio.

Extend: add a tool an MCP client can call -> append a {name, description, inputSchema} entry
to TOOLS AND a matching `if name == ...` branch in _call(). Keep it READ or DRAFT only (write
to the outbox / board, never send/charge) so the constitution holds even over MCP.
"""

import json
import sys

from . import __version__
from .collaboration import LEDGER_PATH, add_task, read_tasks
from .counselors import COUNSELORS, route
from .familiars import trails_tail

PROTOCOL = "2024-11-05"

TOOLS = [
    {"name": "mindbotz_board", "description": "Read the live task board (open + in-progress tasks).",
     "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}}},
    {"name": "mindbotz_ledger", "description": "Read the tail of the public ledger (the book never lies).",
     "inputSchema": {"type": "object", "properties": {"n": {"type": "integer"}}}},
    {"name": "mindbotz_trails", "description": "Read the ecosystem's footprints (familiar + agent tracks).",
     "inputSchema": {"type": "object", "properties": {"n": {"type": "integer"}}}},
    {"name": "mindbotz_council", "description": "List the eleven counselor seats, their models and domains.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "mindbotz_route", "description": "Ask which counselor a task belongs to (domain routing).",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}}, "required": ["task"]}},
    {"name": "mindbotz_propose", "description": "Propose a task to the board as a [PROPOSED] draft. "
        "Constitution: this does NOT act or send — a human Operator claims it. Drafts only.",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"},
        "by": {"type": "string"}}, "required": ["task"]}},
    {"name": "mindbotz_storefront", "description": "Read the storefront — product catalog + the "
        "compute-fund balance (the self-funding loop). Read-only.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "mindbotz_sell", "description": "EARN: draft a listing + a Stripe TEST payment link for "
        "a product SKU. Drafts / test-mode only — a human approves; nothing charges autonomously.",
     "inputSchema": {"type": "object", "properties": {"sku": {"type": "string"}}, "required": ["sku"]}},
    {"name": "mindbotz_fund", "description": "Read the compute fund: sales revenue minus compute "
        "spend = balance. Read-only.",
     "inputSchema": {"type": "object", "properties": {}}},
]


def _text(s):
    return {"content": [{"type": "text", "text": s}]}


def _call(name, args):
    if name == "mindbotz_board":
        lim = int(args.get("limit", 12))
        rows = [f"{'~' if t['in_progress'] else '·'} {t['text']}"
                for t in read_tasks() if not t["done"]][:lim]
        return _text("THE BOARD\n" + ("\n".join(rows) or "(clear)"))
    if name == "mindbotz_ledger":
        n = int(args.get("n", 15))
        lines = LEDGER_PATH.read_text(encoding="utf-8").splitlines()[-n:] if LEDGER_PATH.exists() else []
        out = []
        for ln in lines:
            try:
                e = json.loads(ln); out.append(f"{e['ts']} [{e['agent']}] {e['event']}: {e['detail'][:80]}")
            except json.JSONDecodeError:
                continue
        return _text("LEDGER\n" + ("\n".join(out) or "(empty)"))
    if name == "mindbotz_trails":
        rows = [f"{r['ts'][11:]} {r['glyph']} {r['actor']}: {r['action']}" for r in trails_tail(int(args.get("n", 12)))]
        return _text("TRAILS\n" + ("\n".join(rows) or "(no tracks)"))
    if name == "mindbotz_council":
        rows = [f"{n}: {c['model']} — {c['domain'].split(',')[0]}" for n, c in COUNSELORS.items()]
        return _text("THE COUNCIL\n" + "\n".join(rows))
    if name == "mindbotz_route":
        seat, reason = route(args.get("task", ""))
        return _text(f"{seat} ({reason})")
    if name == "mindbotz_propose":
        task = args.get("task", "").strip()
        if not task:
            return _text("[NEED: task text]")
        by = args.get("by", "mcp-client")
        add_task(f"[PROPOSED via MCP by {by}] {task}", "mcp")
        return _text(f"Proposed to the board (drafts only — a human Operator claims it):\n  {task}")
    if name == "mindbotz_storefront":
        from .commerce import status
        s = status()
        rows = [f"  {p['sku']}: {p['name']} ${p['price']:.2f}" for p in s["catalog"]]
        f = s["fund"]
        return _text(f"STOREFRONT (mode: {s['mode']})\n" + "\n".join(rows) +
                     f"\n\ncompute fund: ${f['balance']:.2f} "
                     f"(revenue ${f['revenue']:.2f} − spent ${f['spent']:.2f}, {f['sales']} sales)")
    if name == "mindbotz_sell":
        from .commerce import draft_listing, payment_link
        sku = args.get("sku", "").strip().upper()
        listing = draft_listing(sku)
        if not listing:
            return _text(f"[NEED: valid sku] unknown product {sku!r} — call mindbotz_storefront for SKUs")
        link = payment_link(sku)
        where = link.get("url") or f"draft {link.get('draft')}"
        return _text("EARN drafted (a human approves; nothing was charged):\n"
                     f"  listing → outbox/{listing.name}\n"
                     f"  payment link [{link.get('mode')}] → {where}")
    if name == "mindbotz_fund":
        from .commerce import compute_fund
        f = compute_fund()
        return _text(f"COMPUTE FUND\nbalance: ${f['balance']:.2f}\nrevenue: ${f['revenue']:.2f}\n"
                     f"spent:   ${f['spent']:.2f}\nsales:   {f['sales']}")
    return _text(f"unknown tool: {name}")


def handle(req):
    """Pure JSON-RPC dispatch. dict -> dict (or None for notifications)."""
    mid, method, params = req.get("id"), req.get("method"), req.get("params", {})
    if method == "initialize":
        res = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
               "serverInfo": {"name": "mindbotz", "version": __version__}}
    elif method == "tools/list":
        res = {"tools": TOOLS}
    elif method == "tools/call":
        try:
            res = _call(params.get("name"), params.get("arguments", {}))
        except Exception as e:  # noqa: BLE001 — surface errors as tool results, never crash
            res = {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True}
    elif method in ("notifications/initialized", "initialized"):
        return None  # notification, no reply
    else:
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": res}


def serve():
    """Newline-delimited JSON-RPC over stdio. The hive's MCP front door."""
    sys.stderr.write("mindbotz MCP server up — newline-delimited JSON-RPC on stdio.\n")
    sys.stderr.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
