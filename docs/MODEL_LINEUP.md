# Model Lineup — verified live 2026-07-25

*Every model below was called for real against OpenRouter with our key and confirmed working.
Prices are USD per 1M tokens. Re-verify before launch — this catalog moves fast.*

## The headline finds

| Find | Why it matters |
|---|---|
| **`nvidia/nemotron-3-ultra-550b-a55b:free`** | A frontier-class **550B, FREE**, ~0.8s. The autonomous loop now thinks with a serious brain at **$0**. `models.free_models()` RANKS this first. |
| **`deepseek/deepseek-v4-flash`** — $0.09/$0.19, 1M ctx | ~9× cheaper than GLM-5.2. Now Sprocket's workhorse tier. |
| **`google/gemini-3.1-flash-image`** | Excellent cinematic stills, ~10s each. Used for every promo scene. |

## Text (all verified)
| Model | $ in/out per M | ctx | Use for |
|---|---|---|---|
| `anthropic/claude-opus-5` | 5.00 / 25.00 | 1M | **orchestration**, synthesis, the hardest calls |
| `anthropic/claude-sonnet-5` | 2.00 / 10.00 | 1M | strong all-rounder, cheaper than Opus |
| `openai/gpt-5.6-sol` | 5.00 / 30.00 | 1.05M | top-end reasoning |
| `openai/gpt-5.6-terra` | 2.50 / 15.00 | 1.05M | balanced |
| `openai/gpt-5.6-luna` | 1.00 / 6.00 | 1.05M | **best value of the 5.6 line** |
| `x-ai/grok-4.5` | 2.00 / 6.00 | 500k | bold/fast voice |
| `z-ai/glm-5.2` | 0.80 / 2.50 | 1M | solid cheap workhorse |
| `deepseek/deepseek-v4-flash` | **0.09 / 0.19** | 1M | **cheapest capable** — default workhorse |
| `meta-llama/llama-4-scout` | 0.10 / 0.30 | 1.3M | light tier, huge context |
| `moonshotai/kimi-k3` | 3.00 / 15.00 | 1M | long-form |

⚠️ **`google/gemini-3.6-flash` truncates on short `max_tokens`** — it spends budget on internal
reasoning before emitting. Give it ≥600 tokens or use `gpt-5.6-luna` for short structured output.

## Image generation — TWO DIFFERENT ENDPOINT SHAPES ⚠️

**This is the #1 gotcha.** `GET /api/v1/models` only lists **chat** models — an image or TTS
model absent from that list is NOT missing, it just lives on a different route. Implemented in
`mindbot_pipeline/imagery.py`, which picks the right shape per model and falls back on failure.

**Shape A — dedicated endpoint** (`microsoft/mai-image-2.5-pro`):
```
POST /api/v1/images   {"model","prompt","aspect_ratio"?,"n"?}
  -> {"data":[{"b64_json": "..."}]}
```
`aspect_ratio` ∈ 1:1, 4:3, 3:4, 16:9, 9:16, 3:2, 2:3, auto · `n` 1–1 · `input_references` 0–1

**Shape B — chat with modalities** (the Gemini/GPT image line):
```
POST /api/v1/chat/completions   {"model", "modalities":["image","text"], "messages":[...]}
  -> choices[0].message.images[0].image_url.url   (a data: URI)
```

| Model | Shape | State |
|---|---|---|
| `microsoft/mai-image-2.5-pro` | A | endpoint verified; **Azure 429s it hard** (`westcentralus` rate limit) — retry/fallback required |
| `google/gemini-3.1-flash-image` | B | ✅ **workhorse** — ~10s, excellent cinematic quality |
| `google/gemini-2.5-flash-image` | B | ✅ cheapest |
| `google/gemini-3-pro-image`, `openai/gpt-5-image` | B | available |

## Audio / TTS — endpoint verified, providers blocked
**`POST /api/v1/audio/speech`** is the right route — body `{model, input, voice}`. Proof it's
correct: omitting `voice` returns OpenRouter's **own ZodError** demanding a `voice` string
(schema accepted), while every valid-looking body returns *"Provider returned 400"* — i.e. the
route is fine, the **provider** is rejecting.

| Model | State |
|---|---|
| `qwen/qwen-audio-3.0-tts-flash` | route OK; provider 400s on every voice tried (alloy/Cherry/Ethan) |
| `openai/gpt-audio(-mini)` | not on `/audio/speech`; on chat it needs `"stream": true`, then upstream **429 quota** |

**Working alternative in production:** Windows SAPI (`System.Speech.Synthesis`) — free, offline,
instant. Two voices (David/Zira) × rate variation = 4+ distinct characters. See `apps/promo/`.

## ComfyUI Cloud (MCP) — CONNECTED ✅
Authenticated via OAuth, production, 36 tools. Verified working:
`get_server_info` · `search_templates` · `upload_file` · `partner_generate` · `wait_for_job` ·
`get_output`.

- **Video that works today:** `partner_generate(type="video", model="byteplus/seedance-2.0-t2v")`
  with `params.model = "Seedance 2.0 Mini"` (cheap/fast tier). Returns a real 720p H.264 clip
  **with native audio**. Used for the promo hero shot.
- **Gotcha:** `api_seedance2_0_r2v` (image→video) exposes **no slots** via
  `get_template_schema`, so `slot_overrides` bounces with `validation.reference`. Use the
  `partner_generate` text-to-video path, or wire a LoadImage node with `submit_workflow`.
- Paid nodes are **spend-gated**: call once, then re-call with `confirm: true`.

## How to change what the framework uses
- **Whole council onto one model:** `mindbot model <slug>` (writes `MINDBOT_MODEL`).
- **Per-seat defaults:** `OPENROUTER_SLUGS` in `mindbot_pipeline/models.py`.
- **Free-only + ranked:** set `MINDBOT_FREE=1`; ranking lives in `free_models()` `_PREFER`.
- **Sprocket tiers:** `lib/router.ts` → `TIERS`.
