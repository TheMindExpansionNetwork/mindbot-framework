# STRESS TEST RESULTS — raw logs

Real output from `bench.py --sweep` against a live S0N1C endpoint on 2026-06-14.
Model: `unsloth/diffusiongemma-26B-A4B-it` (bf16) · GPU: A100-80GB · `max_num_seqs=4`
· `max_tokens=200` · each level fires `concurrency × 2` requests. Nothing here is
hand-edited — it's what the tool printed.

## Run 1 — cold-ish (first sweep after the GPU woke)
```
  S0N1C STRESS SWEEP — max_tokens=200
  ------------------------------------------------------------------------------
  c=1   n=2   ok=2     1.87s   1.07/s req     57.6/s tok  p50=   959ms p95=   959ms
  c=2   n=4   ok=4    26.42s   0.15/s req      7.5/s tok  p50= 25411ms p95= 25539ms
  c=4   n=8   ok=8     2.92s   2.74/s req    144.1/s tok  p50=  1368ms p95=  1607ms
  c=8   n=16  ok=16    4.98s   3.21/s req    163.8/s tok  p50=  2129ms p95=  2837ms
  ------------------------------------------------------------------------------
  peak throughput: 163.8/s tokens at concurrency 8
```
Note the `c=2` line: one request stalled at ~25s (min was 846ms, max 25539ms) — a
warm-up/scheduling outlier on a not-fully-warm GPU. Honest to report; it disappears warm.

## Run 2 — warm (steady state)
```
  S0N1C STRESS SWEEP — max_tokens=200
  ------------------------------------------------------------------------------
  c=1   n=2   ok=2     1.70s   1.18/s req     59.0/s tok  p50=   881ms p95=   881ms
  c=2   n=4   ok=4     2.08s   1.92/s req     93.5/s tok  p50=  1026ms p95=  1057ms
  c=4   n=8   ok=8     3.01s   2.66/s req    130.6/s tok  p50=  1316ms p95=  1704ms
  c=8   n=16  ok=16    5.00s   3.20/s req    163.3/s tok  p50=  2191ms p95=  2638ms
  ------------------------------------------------------------------------------
  peak throughput: 163.3/s tokens at concurrency 8
```

## Live UI swarm (8 personas, concurrent)
```
8/8 agents answered in 3.63s wall (concurrent) · aggregate 59.4 tok/s
```

## Reading the curve
- **Throughput scales with concurrency**: 59 → 93 → 131 → 163 tok/s (1→2→4→8). The GPU
  batches diffusion canvases, so more in-flight requests = more total tokens/sec.
- **Latency degrades gracefully**: p50 881 → 2191 ms across the same range. Beyond
  `max_num_seqs=4`, requests queue, so p95 climbs (2638 ms at c=8).
- **Single-stream is canvas-bound**: a lone request pays the full 256-token denoise cost
  regardless of how short the answer is — which is exactly why the swarm pattern wins.
- **To go wider/faster**: raise `max_num_seqs` on the server (more VRAM per the diffusion
  state buffers), or move to FP8/L40S or NVFP4/B200. bf16/A100 is the safe baseline here.

*Measured, not claimed. The book never lies. 🌒*
