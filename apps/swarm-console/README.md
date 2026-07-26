# S0N1C // Swarm Console

A **stdlib-only, full-stack web console for a diffusion LLM.** No pip, no framework,
no build step — just Python 3.10+ and the URL of an S0N1C endpoint (DiffusionGemma-26B
served serverless on [Modal](https://modal.com)). Open it and you can:

- **CHAT** with the diffusion model and watch live tokens/sec,
- launch a **SWARM** — N counselor personas firing at the model *at once*, and
- run a **STRESS TEST** that sweeps concurrency and charts throughput.

It's three things the M1NDB0TZ project actually needed in one tab: a public demo of the
model, a way to *see* a diffusion swarm, and a benchmark to know how fast it really is.

> **What's a diffusion LLM?** Instead of writing one token at a time, DiffusionGemma
> denoises a whole 256-token *canvas* in parallel. The surprising consequence — measured
> below — is that a single request is **latency-bound** (you pay the canvas cost even for
> a short answer), but aggregate **throughput scales hard with concurrency**. That's why
> a *swarm* on a diffusion model is interesting: many agents share the batched canvases.

```
  S0N1C // SWARM CONSOLE        [ endpoint wired · sonic ]
  [ CHAT ]  [ SWARM ]  [ STRESS ]
  8/8 agents answered in 3.63s wall (concurrent) · aggregate 59.4 tok/s
  ┌ Sage ──────────┐ ┌ Forge ─────────┐ ┌ Spark ─────────┐ ...
  │ Forge a decen- │ │ Codify a trans-│ │ Iterate fast on│
  │ tralized proto-│ │ parent contrib-│ │ the canvas ... │
  │ col ... 34 tok │ │ ution ... 41tok│ │ ... 28 tok     │
  └────────────────┘ └────────────────┘ └────────────────┘
```

---

## Run it
```bash
# point it at your S0N1C endpoint (see the M1NDB0TZ modal/ folder to deploy one)
export SONIC_URL=https://<workspace>--sonic-diffusiongemma-serve.modal.run/v1   # mac/linux
set SONIC_URL=https://<workspace>--sonic-diffusiongemma-serve.modal.run/v1      # windows

python server.py            # -> http://localhost:8799
```
Optional env: `PORT` (default 8799), `SONIC_MODEL` (default `sonic`), `SONIC_KEY`.

### Just the benchmark (no UI)
```bash
python bench.py --url $SONIC_URL --sweep            # the concurrency curve
python bench.py --url $SONIC_URL --concurrency 8 --requests 16 --max-tokens 200
```

---

## How fast is it? (real numbers, measured 2026-06-14)
DiffusionGemma-26B-A4B (bf16) on a single **A100-80GB**, `max_num_seqs=4`, 200 max tokens,
warm. Each level fires `concurrency × 2` requests. Full logs in [RESULTS.md](RESULTS.md).

| concurrency | wall (s) | req/s | **tokens/s** | p50 ms | p95 ms |
|---|---|---|---|---|---|
| 1 | 1.70 | 1.18 | 59.0 | 881 | 881 |
| 2 | 2.08 | 1.92 | 93.5 | 1026 | 1057 |
| 4 | 3.01 | 2.66 | 130.6 | 1316 | 1704 |
| 8 | 5.00 | 3.20 | **163.3** | 2191 | 2638 |

**The finding:** throughput nearly **triples (59 → 163 tok/s)** from 1 → 8 concurrent
requests while p50 latency only rises 881 → 2191 ms. Single-stream is canvas-bound;
the swarm is where a diffusion model earns its keep. (A cold run showed one 25s stall at
c=2 — a warm-up/scheduling outlier; the warm curve above is the steady state.)

Live through the UI: **8 counselor personas answered in 3.63s wall, concurrent.**

---

## Architecture (all of it)
```
S0N1C-SWARM-CONSOLE/
  server.py          # stdlib http.server (ThreadingHTTPServer) — serves UI + proxies S0N1C
  bench.py           # stdlib concurrent load tester (also imported by server.py)
  static/index.html  # the sci-fi console (vanilla JS, canvas chart) — one file, no deps
  RESULTS.md         # raw stress-test logs
  run.sh / run.ps1   # one-line launchers
```
- **Backend** (`server.py`): `ThreadingHTTPServer` so swarm/bench fan out concurrently.
  Routes: `GET /` (UI), `GET /api/config`, `POST /api/chat`, `POST /api/swarm`,
  `POST /api/bench`. It's a thin, honest proxy to the OpenAI-compatible S0N1C endpoint —
  no key handling beyond a passthrough bearer, no state, no fabrication.
- **Bench** (`bench.py`): fires requests via a thread pool, uses the server's
  `usage.completion_tokens` for accurate token counts, reports req/s, tokens/s, and
  latency p50/p95.
- **Frontend** (`static/index.html`): three tabs (Chat / Swarm / Stress), a live canvas
  bar chart for the throughput sweep, zero dependencies, zero build.

## Why stdlib-only
This is part of M1NDB0TZ — an honest, forkable AI collective meant to run on a Raspberry
Pi, in WSL, offline, in 2045. No pip in the loop. If you have Python and a URL, it runs.

## Deploy your own S0N1C
The endpoint this console talks to is DiffusionGemma served on Modal. The deploy app +
runbook live in the main M1NDB0TZ repo under `modal/` (`sonic_diffusiongemma.py`):
pre-download weights on CPU, `modal deploy`, copy the URL, done. Scale-to-zero, so idle
costs $0.

## License
Apache-2.0. Built by the M1NDB0TZ collective. The loop is the magic. 🌒
