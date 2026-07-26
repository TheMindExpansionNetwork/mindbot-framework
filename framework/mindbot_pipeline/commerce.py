"""commerce — the council's earn / spend / operate layer (the Hermes-hackathon core).

The premise of the Hermes Agent Business Hackathon (NVIDIA x Stripe x Nous): agents that can
EARN, SPEND, and RUN REAL OPERATIONS. This module gives the MindBot council exactly that —
WITHOUT breaking the constitution:

    Agent DRAFTS every money action -> outbox + ledger -> a HUMAN approves -> money moves.

Nothing here charges a card, pays a supplier, or moves real funds on its own. The "spend"
functions write drafts a human sends; sales are *recorded* (bookkeeping), not initiated; and
the optional Stripe integration is **test-mode only** (an `sk_test_` key) and only ever
creates a payment *link* — it never captures a charge autonomously.

Stdlib-only by default. Real Stripe calls require the optional extra:  pip install 'mindbot[commerce]'
and a test key in the env:  STRIPE_TEST_KEY=sk_test_...

The flywheel this enables: sales -> compute fund -> GPU time -> more agents -> more to sell.
See docs/HERMES_HACKATHON.md and docs/BUSINESS_GLOW.md.

Extend: add a product -> append to DEMO_CATALOG (or drop a commerce/catalog.json that overrides
it); add a money action -> write a new draft_* helper that calls _draft() (NEVER send/charge);
add bookkeeping -> append a row type via record_* + tally it in compute_fund(); restyle the
storefront -> edit _STORE_TMPL ({{...}} are literal braces, single {name} are .format() fields).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from mindbot_pipeline.collaboration import PIPE_DIR, ROOT, ledger, now

# ── storage (plain JSON, parseable until 2045) ───────────────────────────────
COMMERCE_DIR = PIPE_DIR / "commerce"
OUTBOX = PIPE_DIR / "outbox"
CATALOG_PATH = COMMERCE_DIR / "catalog.json"
ORDERS_PATH = COMMERCE_DIR / "orders.jsonl"   # one line per sale OR compute spend

# The catalog. DIGITAL/support items first — zero inventory, zero shipping, ~100% margin,
# **sellable the moment a Stripe key exists** (the fastest path to a real first dollar). Glow
# physical line after (needs sourcing/shipping). Override via commerce/catalog.json.
DEMO_CATALOG = [
    # ── instant-sellable: digital + support (no inventory, no shipping) ──
    {"sku": "SUPPORT-5", "name": "Compute Fund — Spark", "cost": 0, "price": 5.00, "digital": True,
     "desc": "Buy the swarm ~minutes of GPU. Fund open, self-running AI. Instant, no shipping."},
    {"sku": "SUPPORT-25", "name": "Compute Fund — Booster", "cost": 0, "price": 25.00, "digital": True,
     "desc": "Power a day of the council's fleet. Your name in the supporters ledger."},
    {"sku": "SUPPORT-100", "name": "Compute Fund — Patron", "cost": 0, "price": 100.00, "digital": True,
     "desc": "Patron tier — a week of compute. Founding supporter status."},
    {"sku": "GUIDE", "name": "Build-Your-Own-Agent Guide", "cost": 0, "price": 19.00, "digital": True,
     "desc": "The MindBot playbook: clone, install, run your own self-funding agent. Instant download."},
    {"sku": "SKILLPACK", "name": "MindBot Hermes Skill Pack", "cost": 0, "price": 29.00, "digital": True,
     "desc": "The storefront/council/flywheel SKILL.md pack for Hermes. Instant download."},
    # ── physical glow line (sourcing + shipping; see BUSINESS_GLOW.md) ──
    {"sku": "GLOW-KIT-1", "name": "MindBot Rave Pack", "cost": 2.50, "price": 12.99,
     "desc": "Glow sticks + LED bracelet + bubble wand in one eclipse-branded kit."},
    {"sku": "BUBBLE-GUN", "name": "Eclipse Bubble Blaster", "cost": 3.00, "price": 14.99,
     "desc": "Rapid-fire bubble gun. Crowd-pleaser, made for short-form video."},
    {"sku": "LED-RING-10", "name": "Neon Finger Lights (10-pack)", "cost": 1.20, "price": 9.99,
     "desc": "Ten multicolor LED finger lights. Festival staple, impulse-buy price."},
    {"sku": "STICKER-ECL", "name": "Eclipse Logo Sticker", "cost": 0.80, "price": 4.99,
     "desc": "Print-on-demand. Zero inventory — prints on order. Every sale is an ad."},
]


def _ensure() -> None:
    COMMERCE_DIR.mkdir(parents=True, exist_ok=True)
    OUTBOX.mkdir(parents=True, exist_ok=True)


def _stamp() -> str:
    """A filesystem-safe timestamp for draft filenames."""
    return now().replace(" ", "-").replace(":", "")


def catalog() -> list[dict]:
    """Load the product catalog (your catalog.json if present, else the demo line)."""
    if CATALOG_PATH.exists():
        try:
            return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — corrupt file shouldn't crash the council
            pass
    return DEMO_CATALOG


def _product(sku: str) -> dict | None:
    return next((p for p in catalog() if p["sku"] == sku), None)


def _draft(slug: str, title: str, body: str, event: str) -> Path:
    """Write a human-gated draft to the outbox and log it. NEVER sends. Returns the path."""
    _ensure()
    path = OUTBOX / f"{_stamp()}_commerce_{slug}.md"
    path.write_text(f"# {title}\n\n*Draft — a human reviews and sends/pays. "
                    f"Nothing was transmitted.*\n\n{body}\n", encoding="utf-8")
    ledger(event, f"{title} -> {path.name}", "commerce")
    return path


# ── EARN: drafts that help sell (human posts/sends) ──────────────────────────
def draft_listing(sku: str) -> Path | None:
    """Draft a marketplace listing for a product. Human posts it."""
    p = _product(sku)
    if not p:
        return None
    margin = round((p["price"] - p["cost"]) / p["price"] * 100)
    body = (f"**{p['name']}**  (`{p['sku']}`)\n\n{p['desc']}\n\n"
            f"- Price: ${p['price']:.2f}  ·  Cost: ${p['cost']:.2f}  ·  Margin: ~{margin}%\n"
            f"- Tags: glow, rave, festival, led, party, mindbot\n\n"
            f"Suggested blurb: \"Light up the night with the {p['name']} — "
            f"eclipse-grade glow for your next set.\"")
    return _draft(p["sku"].lower(), f"Listing draft — {p['name']}", body, "listing_drafted")


def draft_supplier_po(sku: str, qty: int) -> Path | None:
    """Draft a purchase order to a supplier. Human sends + pays."""
    p = _product(sku)
    if not p:
        return None
    body = (f"PO request — **{qty} × {p['name']}** (`{p['sku']}`)\n\n"
            f"- Est. unit cost: ${p['cost']:.2f}  ·  Est. total: ${p['cost'] * qty:.2f}\n"
            f"- [NEED: human] confirm supplier, get a real quote, place + pay the order.\n"
            f"- Reminder: order a small sample batch first to validate quality.")
    return _draft(f"po-{p['sku'].lower()}", f"Supplier PO draft — {qty}× {p['name']}",
                  body, "supplier_po_drafted")


# ── SPEND: a request to fund compute (human pays) ────────────────────────────
def draft_compute_topup(amount: float, reason: str = "fleet GPU time") -> Path:
    """Draft a request to spend from the compute fund. Human approves + pays."""
    fund = compute_fund()
    body = (f"Compute top-up request: **${amount:.2f}** for {reason}.\n\n"
            f"- Compute fund balance: ${fund['balance']:.2f} "
            f"(revenue ${fund['revenue']:.2f} − spent ${fund['spent']:.2f})\n"
            f"- [NEED: human] approve + pay (Modal / cloud). The agent only requests.")
    return _draft("compute-topup", f"Compute top-up request — ${amount:.2f}",
                  body, "compute_topup_drafted")


# ── bookkeeping: record what actually happened (no money moves here) ─────────
def record_sale(sku: str, qty: int, amount: float, channel: str = "manual") -> dict:
    """Record a sale that already happened (test-mode or real, entered by a human/flow)."""
    _ensure()
    row = {"ts": now(), "type": "sale", "sku": sku, "qty": qty,
           "amount": round(amount, 2), "channel": channel}
    with ORDERS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    ledger("sale_recorded", f"{qty}× {sku} = ${amount:.2f} ({channel})", "commerce")
    return row


def record_compute_spend(amount: float, reason: str = "fleet") -> dict:
    """Record approved compute spend against the fund (entered after a human pays)."""
    _ensure()
    row = {"ts": now(), "type": "compute", "amount": round(amount, 2), "reason": reason}
    with ORDERS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    ledger("compute_spend_recorded", f"${amount:.2f} ({reason})", "commerce")
    return row


def _orders() -> list[dict]:
    if not ORDERS_PATH.exists():
        return []
    out = []
    for line in ORDERS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:  # noqa: BLE001 — skip a bad line, don't crash
                pass
    return out


def compute_fund() -> dict:
    """The flywheel ledger: revenue from sales − approved compute spend = balance."""
    # Tally keys off the "type" tag written by record_sale / record_compute_spend — a new row
    # type stays invisible to the fund until summed here.
    rows = _orders()
    revenue = round(sum(r["amount"] for r in rows if r.get("type") == "sale"), 2)
    spent = round(sum(r["amount"] for r in rows if r.get("type") == "compute"), 2)
    return {"revenue": revenue, "spent": spent, "balance": round(revenue - spent, 2),
            "sales": sum(1 for r in rows if r.get("type") == "sale")}


# ── REAL Stripe over stdlib urllib (no SDK needed — fits the 2045 rule) ───────
# A payment LINK never charges anyone by itself — a customer must choose to pay it. The agent
# only creates the link. LIVE keys require an explicit MINDBOT_STRIPE_LIVE=1 opt-in so we can
# never accidentally bill real cards while developing.
def _stripe_key() -> str:
    return os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_TEST_KEY") or ""


def stripe_mode() -> str:
    """'test' (sk_test_), 'live' (sk_live_ AND MINDBOT_STRIPE_LIVE=1), 'blocked' (live key but
    not opted in — we refuse), or 'draft' (no key — safe stub)."""
    key = _stripe_key()
    if key.startswith("sk_test_"):
        return "test"
    if key.startswith("sk_live_"):
        return "live" if os.environ.get("MINDBOT_STRIPE_LIVE") == "1" else "blocked"
    return "draft"


def _stripe_post(path: str, params: dict, key: str) -> dict:
    """POST form-encoded params to the Stripe REST API. Stdlib only."""
    import urllib.parse
    import urllib.request
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        "https://api.stripe.com/v1/" + path, data=data,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def payment_link(sku: str) -> dict:
    """Create a REAL Stripe Payment Link for a product (test or live), or draft the intent.

    Returns a shareable URL the moment a Stripe key is set — that is the immediate-money path:
    share the link, a customer pays, the money lands in YOUR Stripe account. The agent never
    captures funds; it only makes the link. Live mode needs MINDBOT_STRIPE_LIVE=1.
    """
    p = _product(sku)
    if not p:
        return {"ok": False, "error": f"unknown sku {sku}"}
    mode = stripe_mode()
    if mode in ("draft", "blocked"):
        why = ("a live key is present but MINDBOT_STRIPE_LIVE=1 is not set (safety) — refusing "
               "to create a live link" if mode == "blocked"
               else "set STRIPE_TEST_KEY=sk_test_... (or STRIPE_API_KEY) to create a real link")
        path = _draft(f"paylink-{p['sku'].lower()}", f"Payment-link intent — {p['name']}",
                      f"Would create a Stripe payment link for {p['name']} at ${p['price']:.2f}.\n{why}.",
                      "paylink_drafted")
        return {"ok": True, "mode": "draft", "draft": path.name, "note": why}
    key = _stripe_key()
    try:
        price = _stripe_post("prices", {
            "unit_amount": int(round(p["price"] * 100)), "currency": "usd",
            "product_data[name]": p["name"]}, key)
        link = _stripe_post("payment_links", {
            "line_items[0][price]": price["id"], "line_items[0][quantity]": 1}, key)
        ledger(f"paylink_{mode}", f"{p['name']} ${p['price']:.2f} -> {link.get('url')}", "commerce")
        return {"ok": True, "mode": mode, "sku": sku, "price": p["price"], "url": link.get("url")}
    except Exception as e:  # noqa: BLE001 — surface the Stripe error, never crash the caller
        return {"ok": False, "mode": mode, "error": str(e)}


def build_store(out_path: Path | None = None) -> Path:
    """Generate a shareable static storefront (store/index.html) from the catalog.

    Each product gets a Buy button → its Stripe Payment Link (created live if a key is set, else
    a '#' placeholder + a note). Host the file anywhere (GitHub Pages, Netlify drop) and sell.
    """
    out_path = out_path or (ROOT / "store" / "index.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mode = stripe_mode()
    cards = []
    for p in catalog():
        # Live/test: one Stripe round-trip per product (creates a price + a payment link each).
        link = payment_link(p["sku"]) if mode in ("test", "live") else {"mode": "draft"}
        href = link.get("url") or "#"
        badge = "DIGITAL · instant" if p.get("digital") else "ships"
        cards.append(
            f'<div class="card"><div class="badge">{badge}</div><h2>{p["name"]}</h2>'
            f'<p>{p["desc"]}</p><div class="row"><span class="price">${p["price"]:.2f}</span>'
            f'<a class="buy" href="{href}" target="_blank" rel="noopener">Buy</a></div></div>')
    note = ("" if mode in ("test", "live") else
            '<p class="note">⚠ Set STRIPE_TEST_KEY (or STRIPE_API_KEY) and re-run '
            '<code>mindbot commerce --store</code> to wire live Buy buttons.</p>')
    html = _STORE_TMPL.format(mode=mode, cards="\n".join(cards), note=note, ts=now())
    out_path.write_text(html, encoding="utf-8")
    ledger("store_built", f"{out_path} (mode={mode}, {len(cards)} products)", "commerce")
    return out_path


_STORE_TMPL = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MindBot Store — fund the swarm</title>
<style>
 :root{{--bg:#0a0a12;--card:#14141f;--neon:#32e6c8;--amber:#ffb300;--fg:#e8e8f0}}
 *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.5 system-ui,sans-serif;padding:2rem}}
 header{{text-align:center;margin-bottom:2rem}}
 h1{{color:var(--neon);margin:.2rem;font-size:2rem}} .sub{{color:#9aa}}
 .grid{{display:grid;gap:1rem;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));max-width:980px;margin:0 auto}}
 .card{{background:var(--card);border:1px solid #262636;border-radius:14px;padding:1.2rem;position:relative}}
 .badge{{position:absolute;top:.8rem;right:.8rem;font-size:.7rem;color:var(--amber);
  border:1px solid var(--amber);border-radius:99px;padding:.1rem .5rem}}
 h2{{font-size:1.1rem;margin:.2rem 0 .5rem}} p{{color:#bcbccc;font-size:.92rem;min-height:3em}}
 .row{{display:flex;align-items:center;justify-content:space-between;margin-top:.8rem}}
 .price{{font-size:1.3rem;font-weight:700;color:var(--neon)}}
 .buy{{background:var(--neon);color:#001;font-weight:700;text-decoration:none;
  padding:.5rem 1.1rem;border-radius:99px}}
 .note{{text-align:center;color:var(--amber);max-width:680px;margin:1.5rem auto}}
 footer{{text-align:center;color:#667;margin-top:2rem;font-size:.85rem}}
 code{{background:#001;padding:.1rem .3rem;border-radius:4px;color:var(--neon)}}
</style></head><body>
<header><h1>🌒 MindBot Store</h1>
<div class="sub">Every purchase funds an open, self-running AI council. Stripe mode: <b>{mode}</b>.</div></header>
{note}
<div class="grid">
{cards}
</div>
<footer>Built {ts} · the loop is the magic · payments by Stripe · a human ships physical goods.</footer>
</body></html>"""


def status() -> dict:
    """One dict for the CLI + the /api/commerce dashboard panel."""
    fund = compute_fund()
    return {
        "mode": stripe_mode(),
        "products": len(catalog()),
        "catalog": catalog(),
        "fund": fund,
        "orders": _orders()[-10:],
    }
