---
name: modal-deploy
description: Use to run the hive's own models and jobs on Modal (serverless GPUs) — deploy/serve a model endpoint (S0N1C = DiffusionGemma), launch a diffusion swarm, schedule autonomous cron pulses, or fine-tune on GPU. The cheap-when-idle compute layer. Operator holds the credits; agents draft the apps + commands.
status: active
---

# modal-deploy

## When to use
Whenever the work needs a GPU or a 24/7 schedule the local box can't give: serving our
own model (S0N1C), running a *diffusion swarm* (whole council on one fast model),
scheduling the autonomous pulse, fine-tuning the Mind, or any heavy batch job. Modal
bills only while running + scales to zero, so idle = $0.

## The map (everything lives in `modal/`)
- `modal/sonic_diffusiongemma.py` — S0N1C: DiffusionGemma served OpenAI-compatible on
  an A100-80GB, scale-to-zero, weights cached in a Volume. The hive's own fast model.
- `modal/gateway.py` — cheap CPU web gateway, always reachable, wakes the GPU on demand
  (the "CPU interface → GPU backends" pattern).
- `modal/cron_autonomous.py` — scheduled pulse: the hive works on its own on a cron.
- `modal/README.md` — full deploy/test/cost runbook.

## Steps
1. **Auth (Operator, one-time):** `pip install modal` then `modal token new`.
   This machine is already authed (workspace `m1ndb0t-2045`).
2. **Pre-download weights cheaply (CPU, fails fast if anything's wrong):**
   `modal run modal/sonic_diffusiongemma.py::download`
3. **Deploy the endpoint:** `modal deploy modal/sonic_diffusiongemma.py`
   Copy the printed URL. Wire it in: add `MINDBOT_SONIC_URL=<url>/v1` to `framework/.env`.
4. **Use it:** any counselor whose model is `sonic`/`diffusion-gemma` now routes to S0N1C.
   Flip the WHOLE council onto it (a diffusion swarm) with `MINDBOT_SONIC_ALL=1`.
   Test: `python -m mindbot_pipeline.cli swarmtest`.
5. **Go autonomous:** `modal deploy modal/cron_autonomous.py` — the pulse runs on a
   schedule, drafting to outbox. The law still holds: agent drafts, human sends.

## Output contract
A live Modal endpoint URL + the `.env` line that wires it in, OR a deployed cron app.
Every app is well-commented and machine-portable (constants at the top, swappable
GPU/precision). Never hard-code secrets — keys live in `framework/.env` (gitignored) or
Modal Secrets (`modal secret create ...`).

## Cost discipline (constitution: the ledger never lies, incl. about spend)
- A100-80GB ≈ ~$2.50/hr **only while serving**; scale-to-zero = $0 idle. Test freely.
- Don't pin a hot GPU 24/7 unless asked — that drains a small budget in ~2 days. The
  always-on illusion = cheap CPU gateway + on-demand GPU + scheduled pulse.
- Cheaper precision swaps (once bf16 is proven): FP8→L40S, NVFP4→B200, GGUF→llama.cpp.

## Resources
- Modal's own agent skills: `modal skills install` (docs + patterns into .claude/).
- Examples: https://github.com/modal-labs/modal-examples  ·  docs: https://modal.com/docs
- DiffusionGemma: https://ai.google.dev/gemma/docs/diffusiongemma

## Failure modes
- Gated model → use the ungated `unsloth/` mirror, or add an HF Secret for `google/`.
- Burning credits on a failed boot → always `::download` on CPU first.
- Endpoint cold on first hit → that's the GPU waking (~1–3 min on cold start); the
  router degrades to OpenRouter/local meanwhile, so the pulse never stalls.
