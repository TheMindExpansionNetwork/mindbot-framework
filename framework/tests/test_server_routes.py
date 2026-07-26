"""Every GET /api route must return a JSON-able dict without raising.

The MindBot OS interface polls these; a route that crashes blanks a panel. This catches it.
"""
import json
import unittest

from mindbot_pipeline import server


class TestServerRoutes(unittest.TestCase):
    def test_every_route_returns_a_dict(self):
        for name, fn in server.ROUTES.items():
            with self.subTest(route=name):
                out = fn()
                self.assertIsInstance(out, dict, f"/api/{name} returned {type(out).__name__}")

    def test_routes_are_json_serializable(self):
        for name, fn in server.ROUTES.items():
            with self.subTest(route=name):
                json.dumps(fn())  # raises if not serializable

    def test_fleet_route_present(self):
        self.assertIn("fleet", server.ROUTES)
        self.assertIn("fleet", server.ROUTES["fleet"]())


if __name__ == "__main__":
    unittest.main()
