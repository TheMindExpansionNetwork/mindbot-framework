import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mindbot_pipeline.server import api_all, ROUTES

class TestServer(unittest.TestCase):
    def test_api(self):
        self.assertTrue(set(['version', 'board', 'ledger', 'trails', 'missions', 'employees', 'commons']).issubset(api_all().keys()))
        self.assertTrue(callable(ROUTES['all']))
