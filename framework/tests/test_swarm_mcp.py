"""The two adapters that let swarms + Hermes use this framework:
  - nucleus.swarm  — N councilors pulsing concurrently (mocked pulse: no network, no board writes)
  - the MCP commerce tools — storefront / fund readable by any MCP client (Hermes, Cursor…)
"""
import threading
import unittest

from mindbot_pipeline import mcp_server, nucleus


class TestSwarm(unittest.TestCase):
    def test_swarm_runs_concurrently_and_stops_on_rounds(self):
        """Concurrency is FORCED here, not hoped for.

        The original version mocked an instant pulse and then asserted that more than one worker
        thread had been seen. It passed on Windows and failed on a 2-core Linux CI runner: with a
        no-op pulse, worker 1 burns through all 8 rounds and sets `stop` before the OS has even
        scheduled workers 2-4. The assertion was correct, but the test never created the
        condition it claimed to check — it was measuring thread-startup latency, not the swarm.

        A barrier fixes it properly. Every worker must ARRIVE inside pulse() before any is
        allowed to return, so the swarm cannot satisfy it sequentially. If concurrency ever
        regresses, the barrier times out and this fails loudly instead of passing by luck on a
        platform that happens to start threads slowly.
        """
        WORKERS = 4
        seen_threads, calls, lock = set(), {"n": 0}, threading.Lock()
        gate = threading.Barrier(WORKERS)
        gate_state = {"released": False, "timed_out": False}

        def fake_pulse(agent=None):
            with lock:
                calls["n"] += 1
                seen_threads.add(threading.current_thread().name)
                hold = not gate_state["released"]
            if hold:
                # Only the first round is gated. Afterwards workers run freely, so the barrier
                # can never deadlock once some of them have finished and exited.
                try:
                    gate.wait(timeout=10)
                except threading.BrokenBarrierError:
                    gate_state["timed_out"] = True        # fewer than WORKERS ever arrived
                with lock:
                    gate_state["released"] = True
            return {"agent": "Tester", "worked": "did a thing", "ok": True, "mode": "stage"}

        saved_pulse, saved_ledger = nucleus.pulse, nucleus.ledger
        nucleus.pulse = fake_pulse
        nucleus.ledger = lambda *a, **k: None  # don't touch the real ledger
        try:
            res = nucleus.swarm(workers=WORKERS, rounds=8, idle_stop=999)
        finally:
            nucleus.pulse, nucleus.ledger = saved_pulse, saved_ledger

        self.assertFalse(gate_state["timed_out"],
                         f"the swarm did not run {WORKERS} workers at once — only "
                         f"{len(seen_threads)} thread(s) reached pulse() within 10s")
        self.assertEqual(res["workers"], WORKERS)
        self.assertGreaterEqual(res["pulses"], 8)          # hits the round cap (may overshoot)
        self.assertTrue(res["produced"])
        self.assertEqual(len(seen_threads), WORKERS,
                         "every worker must have pulsed — the barrier proves they overlapped")


class TestMcpCommerceTools(unittest.TestCase):
    def test_new_tools_are_listed(self):
        names = {t["name"] for t in mcp_server.TOOLS}
        for t in ("mindbotz_storefront", "mindbotz_sell", "mindbotz_fund"):
            self.assertIn(t, names)

    def test_storefront_and_fund_are_readable(self):
        out = mcp_server._call("mindbotz_storefront", {})
        self.assertIn("STOREFRONT", out["content"][0]["text"])
        out = mcp_server._call("mindbotz_fund", {})
        self.assertIn("COMPUTE FUND", out["content"][0]["text"])

    def test_tools_call_dispatch_through_handle(self):
        resp = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                  "params": {"name": "mindbotz_fund", "arguments": {}}})
        self.assertIn("result", resp)
        self.assertIn("COMPUTE FUND", resp["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
