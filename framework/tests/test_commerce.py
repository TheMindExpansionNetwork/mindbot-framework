"""commerce: the earn/spend/operate layer. Verify drafts, bookkeeping, and the fund math —
all in a temp dir, with the ledger stubbed so tests never touch real shared state."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from mindbot_pipeline import commerce


class TestCommerce(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._saved = (commerce.COMMERCE_DIR, commerce.OUTBOX,
                       commerce.ORDERS_PATH, commerce.CATALOG_PATH, commerce.ledger)
        commerce.COMMERCE_DIR = Path(self._tmp) / "commerce"
        commerce.OUTBOX = Path(self._tmp) / "outbox"
        commerce.ORDERS_PATH = commerce.COMMERCE_DIR / "orders.jsonl"
        commerce.CATALOG_PATH = commerce.COMMERCE_DIR / "catalog.json"
        commerce.ledger = lambda *a, **k: None  # don't pollute the real ledger

    def tearDown(self):
        (commerce.COMMERCE_DIR, commerce.OUTBOX,
         commerce.ORDERS_PATH, commerce.CATALOG_PATH, commerce.ledger) = self._saved
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_catalog_is_well_formed(self):
        cat = commerce.catalog()
        self.assertGreaterEqual(len(cat), 4)
        for p in cat:
            for key in ("sku", "name", "cost", "price"):
                self.assertIn(key, p)

    def test_draft_listing_writes_outbox(self):
        p = commerce.draft_listing("GLOW-KIT-1")
        self.assertIsNotNone(p)
        self.assertTrue(p.exists())
        self.assertIn("MindBot Rave Pack", p.read_text(encoding="utf-8"))
        self.assertIsNone(commerce.draft_listing("NOPE"))  # unknown sku

    def test_fund_math(self):
        commerce.record_sale("GLOW-KIT-1", 2, 25.98, "test")
        f = commerce.compute_fund()
        self.assertEqual(f["revenue"], 25.98)
        self.assertEqual(f["sales"], 1)
        self.assertEqual(f["balance"], 25.98)
        commerce.record_compute_spend(10.0, "fleet")
        f = commerce.compute_fund()
        self.assertEqual(f["spent"], 10.0)
        self.assertEqual(f["balance"], 15.98)

    def test_status_is_json_serializable(self):
        json.dumps(commerce.status())

    def test_stripe_defaults_to_safe_draft_mode(self):
        # with no Stripe key, nothing can charge — payment_link only drafts (no network)
        self.assertEqual(commerce.stripe_mode(), "draft")
        r = commerce.payment_link("SUPPORT-25")
        self.assertTrue(r["ok"])
        self.assertEqual(r["mode"], "draft")

    def test_has_instant_sellable_digital_skus(self):
        skus = {p["sku"] for p in commerce.catalog()}
        for s in ("SUPPORT-5", "SUPPORT-25", "GUIDE", "SKILLPACK"):
            self.assertIn(s, skus)

    def test_build_store_writes_hostable_html(self):
        out = Path(self._tmp) / "store" / "index.html"
        p = commerce.build_store(out)          # draft mode (no key) -> placeholder buttons, no network
        self.assertTrue(p.exists())
        html = p.read_text(encoding="utf-8")
        self.assertIn("MindBot Store", html)
        self.assertIn("Compute Fund", html)


if __name__ == "__main__":
    unittest.main()
