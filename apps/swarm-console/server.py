#!/usr/bin/env python3
"""S0N1C Swarm Console — a stdlib-only full-stack app for a diffusion LLM.

No pip, no framework, no build step. Just Python 3.10+ and the URL of an S0N1C
(DiffusionGemma-on-Modal) endpoint. Serves a sci-fi web console that can:
  - chat with the diffusion model (live tokens/sec),
  - launch a SWARM (N counselor personas firing at once), and
  - STRESS-TEST throughput across a concurrency sweep.

Run:
  set SONIC_URL=https://<ws>--sonic-diffusiongemma-serve.modal.run/v1   (Windows)
  export SONIC_URL=https://<ws>--sonic-diffusiongemma-serve.modal.run/v1  (mac/linux)
  python server.py            # then open http://localhost:8799  (default port)
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bench import _chat_url, one_request, run_bench

HERE = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "8799"))
SONIC_URL = os.environ.get("SONIC_URL") or os.environ.get("MINDBOT_SONIC_URL", "")
MODEL = os.environ.get("SONIC_MODEL", "sonic")
KEY = os.environ.get("SONIC_KEY", "sonic")

# The swarm's faces — counselor personas, each a distinct lens on the same question.
PERSONAS = [
    ("Sage", "deep synergetic reasoning + ethics"),
    ("Forge", "precision architecture + clean systems"),
    ("Spark", "fast creative iteration on the canvas"),
    ("Seeker", "research + open-source patterns"),
    ("Oracle", "long-horizon planning + foresight"),
    ("Quantum", "math, logic, efficiency"),
    ("Vanguard", "bold real-time building"),
    ("Tempest", "risk, security, hard questions"),
]


def _persona_prompt(name: str, domain: str, question: str) -> tuple[str, str]:
    sys = (f"You are {name}, a counselor of the M1NDB0TZ collective. Lens: {domain}. "
           f"Answer in ONE vivid, concrete sentence — no preamble.")
    # DiffusionGemma has no separate system role in our call; fold persona into the prompt.
    return name, f"[{name} — {domain}]\n{sys}\n\nQuestion: {question}"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet console
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict):
        self._send(code, json.dumps(obj).encode(), "application/json")

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(n).decode()) if n else {}

    # ── routes ────────────────────────────────────────────────────────────
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = (HERE / "static" / "index.html").read_bytes()
            return self._send(200, html, "text/html; charset=utf-8")
        if self.path == "/api/config":
            return self._json(200, {"has_url": bool(SONIC_URL), "model": MODEL,
                                    "personas": [p[0] for p in PERSONAS]})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if not SONIC_URL:
            return self._json(503, {"error": "SONIC_URL not set on the server"})
        try:
            data = self._read_json()
        except Exception:  # noqa: BLE001
            return self._json(400, {"error": "bad json"})

        if self.path == "/api/chat":
            q = data.get("prompt", "Say hello as a diffusion model.")
            mt = int(data.get("max_tokens", 200))
            r = one_request(_chat_url(SONIC_URL), MODEL, q, mt, KEY)
            tok_s = round(r["completion_tokens"] / (r["ms"] / 1000), 1) if r.get("ms") else 0
            return self._json(200, {**r, "tokens_per_s": tok_s})

        if self.path == "/api/swarm":
            q = data.get("prompt", "What's the single most important next move for us?")
            n = max(1, min(int(data.get("n", len(PERSONAS))), len(PERSONAS)))
            mt = int(data.get("max_tokens", 160))
            jobs = [_persona_prompt(nm, dm, q) for nm, dm in PERSONAS[:n]]
            t0 = time.time()
            out = []
            with ThreadPoolExecutor(max_workers=n) as ex:
                def go(job):
                    name, prompt = job
                    r = one_request(_chat_url(SONIC_URL), MODEL, prompt, mt, KEY)
                    return {"name": name, **r}
                out = list(ex.map(go, jobs))
            wall = time.time() - t0
            toks = sum(o["completion_tokens"] for o in out if o["ok"])
            return self._json(200, {
                "agents": out, "wall_s": round(wall, 2),
                "ok": sum(1 for o in out if o["ok"]),
                "tokens_per_s": round(toks / wall, 1) if wall else 0})

        if self.path == "/api/bench":
            c = max(1, min(int(data.get("concurrency", 4)), 32))
            n = max(1, min(int(data.get("requests", 8)), 64))
            mt = int(data.get("max_tokens", 200))
            return self._json(200, run_bench(SONIC_URL, MODEL, _BENCH_PROMPT, n, c, mt, KEY))

        return self._json(404, {"error": "not found"})


_BENCH_PROMPT = ("Describe one bold, honest move an autonomous AI collective should make "
                 "to fund itself while teaching for free. Two sentences.")


def main():
    print(f"  S0N1C Swarm Console -> http://localhost:{PORT}")
    print(f"  endpoint: {SONIC_URL or '(SONIC_URL NOT SET)'}  model={MODEL}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
