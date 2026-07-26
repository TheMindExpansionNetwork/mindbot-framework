# 🎬 MindBot Promo — a fully autonomous video pipeline

A 71-second dystopian comedy ad for MindBot where **every asset was machine-generated** —
script, voices, scenes, hero shot, and the cut. Reproducible end to end with one command.

**Output:** `out/mindbot_promo.mp4` (1280×720, ~71s, H.264 + AAC)

## The gimmick — the ad demonstrates the product
Each character is written by a **different frontier model**, then a separate model orchestrates
them. The film is itself a multi-model council at work:

| Character | Written by | Voice (SAPI) |
|---|---|---|
| NARRATOR (chipper corporate announcer) | `anthropic/claude-opus-5` | Zira, rate +2 |
| THE WORKER (out of thought-credits) | `openai/gpt-5.6-luna` | David, rate −3 |
| THE BILLING BOT (predatory upsell) | `openai/gpt-5.6-terra` | Zira, rate +4 |
| THE AUDITOR (bored bureaucrat) | `openai/gpt-5.6-sol` | David, rate −1 |
| Tagline / orchestration | `anthropic/claude-opus-5` | Zira, rate 0 |

> *"We bill by the credit, the second, and the emotional aftertaste — because innovation needs
> recurring revenue."* — THE BILLING BOT (gpt-5.6-terra)

## The pipeline
```
script     cast.json / tagline.txt   ← 5 models via OpenRouter
scenes     assets/scene_*.png        ← google/gemini-3.1-flash-image (modalities:["image","text"])
hero shot  assets/hero_council.mp4   ← ByteDance Seedance 2.0 Mini via ComfyUI Cloud (partner_generate)
voices     voice/*.wav               ← Windows SAPI (System.Speech) — free, offline, 4 speakers
cut        out/mindbot_promo.mp4     ← build_promo.py (ffmpeg: zoompan Ken Burns + drawtext + amix)
```
No npm, no cloud renderer — just **ffmpeg + Pillow**. (HyperFrames was the intended renderer but
`npx` fails in this environment with `ERR_SSL_CIPHER_OPERATION_FAILED`.)

## Rebuild
```bash
python build_promo.py        # re-cuts from existing assets in ~1 min
```

## Extend it — for the next agent
- **Add/re-order a beat:** edit `BEATS` in `build_promo.py` — a tuple of
  `(kind, source, voice_file, speaker_caption)` where `kind` is `img` | `video` | `card`.
  **Durations are read from the voice files**, so the cut always matches the read — never
  hand-tune timings.
- **New scene art:** generate a PNG into `assets/` (see `docs/MODEL_LINEUP.md` for the image
  API shape), then reference it from a beat.
- **New dialogue:** append to `cast.json`, re-run the SAPI block (it's in the session history /
  reproducible from the voice table above), then rebuild.
- **New motion shot:** `partner_generate(type="video", model="byteplus/seedance-2.0-t2v",
  params={"model":"Seedance 2.0 Mini"})`, download, drop in `assets/`, add a `video` beat.
- **Card design:** `make_cards()` in `build_promo.py` (Pillow). Note the tagline is burned on as
  a *caption*, not baked into the card — drawing it in both places double-prints it.

## Known limits
- SAPI voices are robotic — charming for a dystopian ad, wrong for a serious brand piece. For
  natural VO use ElevenLabs via ComfyUI (`elevenlabs/sound-generation` is SFX; TTS needs a
  different node) or fix the `gpt-audio` quota.
- No background music. `elevenlabs/sound-generation` via `partner_generate` can produce a bed.
- Cuts are hard cuts. Crossfades would need `xfade` between segments.
