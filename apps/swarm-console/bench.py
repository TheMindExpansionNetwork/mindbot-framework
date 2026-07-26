#!/usr/bin/env python3
"""S0N1C stress tester — measure a diffusion LLM under concurrent load.

Stdlib only. Fires N chat-completion requests at a chosen concurrency, then reports
throughput (requests/sec, tokens/sec) and latency percentiles using the server's own
`usage.completion_tokens` for accurate counts.

Why this is interesting for S0N1C specifically: DiffusionGemma denoises a fixed-size
256-token canvas every generation, so a SINGLE request is latency-bound (you pay the
whole canvas cost even for a short answer) — but the GPU batches canvases, so aggregate
TOKENS/SEC climbs as concurrency rises until the server's max_num_seqs saturates. The
sweep below makes that curve visible.

Usage:
  python bench.py --url https://<ws>--sonic-diffusiongemma-serve.modal.run/v1 --sweep
  python bench.py --url <.../v1> --concurrency 4 --requests 8 --max-tokens 200
"""

import argparse
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

DEFAULT_PROMPT = ("Describe one bold, honest move an autonomous AI collective should make "
                  "to fund itself while teaching for free. Two sentences.")


def _chat_url(base: str) -> str:
    b = base.rstrip("/")
    if b.endswith("/chat/completions"):
        return b
    if b.endswith("/v1"):
        return b + "/chat/completions"
    return b + "/v1/chat/completions"


def one_request(url: str, model: str, prompt: str, max_tokens: int, key: str = "sonic") -> dict:
    """Fire a single chat completion; return timing + token usage (never raises)."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            data = json.loads(r.read().decode())
        dt = (time.time() - t0) * 1000
        ct = (data.get("usage") or {}).get("completion_tokens", 0)
        txt = data["choices"][0]["message"]["content"]
        return {"ok": True, "ms": dt, "completion_tokens": ct, "text": txt}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "ms": (time.time() - t0) * 1000, "completion_tokens": 0,
                "error": f"{type(e).__name__}: {str(e)[:80]}"}


def run_bench(url: str, model: str, prompt: str, n: int, concurrency: int,
              max_tokens: int, key: str = "sonic") -> dict:
    """Fire n requests at the given concurrency; return aggregate metrics."""
    chat = _chat_url(url)
    results = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(one_request, chat, model, prompt, max_tokens, key) for _ in range(n)]
        for f in as_completed(futs):
            results.append(f.result())
    wall = time.time() - t0
    ok = [r for r in results if r["ok"]]
    toks = sum(r["completion_tokens"] for r in ok)
    lat = sorted(r["ms"] for r in ok)

    def pct(p: float) -> float:
        return lat[min(len(lat) - 1, int(len(lat) * p))] if lat else 0.0

    return {
        "concurrency": concurrency, "requests": n, "ok": len(ok), "failed": n - len(ok),
        "wall_s": round(wall, 2),
        "req_per_s": round(len(ok) / wall, 2) if wall else 0,
        "total_tokens": toks,
        "tokens_per_s": round(toks / wall, 1) if wall else 0,
        "lat_p50_ms": round(pct(0.5)), "lat_p95_ms": round(pct(0.95)),
        "lat_min_ms": round(lat[0]) if lat else 0,
        "lat_max_ms": round(lat[-1]) if lat else 0,
    }


def print_row(m: dict) -> None:
    print(f"  c={m['concurrency']:<3} n={m['requests']:<3} "
          f"ok={m['ok']:<3} {m['wall_s']:>6.2f}s  "
          f"{m['req_per_s']:>5}/s req  {m['tokens_per_s']:>7}/s tok  "
          f"p50={m['lat_p50_ms']:>6}ms p95={m['lat_p95_ms']:>6}ms")


def sweep(url: str, model: str, prompt: str, max_tokens: int,
          levels=(1, 2, 4, 8), key: str = "sonic") -> list:
    """Run the concurrency curve and print a table. Returns the rows."""
    print(f"\n  S0N1C STRESS SWEEP — max_tokens={max_tokens}\n  {'-' * 78}")
    rows = []
    for c in levels:
        m = run_bench(url, model, prompt, n=c * 2, concurrency=c, max_tokens=max_tokens, key=key)
        print_row(m)
        rows.append(m)
    best = max(rows, key=lambda r: r["tokens_per_s"]) if rows else {}
    print(f"  {'-' * 78}")
    if best:
        print(f"  peak throughput: {best['tokens_per_s']}/s tokens at concurrency "
              f"{best['concurrency']}\n")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Stress-test the S0N1C diffusion endpoint.")
    ap.add_argument("--url", required=True, help="S0N1C base URL (…/v1)")
    ap.add_argument("--model", default="sonic")
    ap.add_argument("--key", default="sonic")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--max-tokens", type=int, default=200)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--requests", type=int, default=8)
    ap.add_argument("--sweep", action="store_true", help="run the 1/2/4/8 concurrency curve")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    a = ap.parse_args()

    if a.sweep:
        rows = sweep(a.url, a.model, a.prompt, a.max_tokens, key=a.key)
        if a.json:
            print(json.dumps(rows, indent=2))
    else:
        m = run_bench(a.url, a.model, a.prompt, a.requests, a.concurrency, a.max_tokens, a.key)
        if a.json:
            print(json.dumps(m, indent=2))
        else:
            print_row(m)


if __name__ == "__main__":
    main()
