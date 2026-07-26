---
name: instructional-video
description: Use to turn a topic or a doc into a narrated instructional/training video — script + Manim animation + TTS voiceover — plus the matching written training doc. The teaching arm of the collective (free education is the mission). Drafts to outbox; the Operator publishes.
status: draft
---

# instructional-video

## When to use
Anything that teaches: a "how M1NDB0TZ works" explainer, a counselor-intro lesson, a
"point an AI at this repo" walkthrough, a concept animation (how a diffusion swarm works),
or a training document with a companion narrated video. Free education is the mission —
this is how we put knowledge in people's hands.

## The stack (three parts, each replaceable)
1. **Script** — written first (use the `screenwriter` skill): beats, narration lines
   (≤15 words ≈ 10s each), and an on-screen cue per beat. Caption-safe (muted viewing).
2. **Animation** — **Manim** (3blue1brown's engine, https://github.com/3b1b/manim) for
   clean concept animations, OR **HyperFrames** (HTML→MP4, already in this repo) for
   slide/title/code-walkthrough style. Pick by content: Manim for math/diagrams,
   HyperFrames for UI/code/brand.
3. **Voice** — **v0x / Higgs Audio v3 TTS** (`modal/voxx_higgs_tts.py`, planned) for
   expressive narration, OR **Kokoro TTS** via `hyperframes tts` (works today, local).

## Steps
1. Lock the spec: audience (beginner?), length, the ONE thing they'll be able to DO after.
   Missing facts → `[NEED: …]`, never invent. Honesty clause holds — never teach a claim
   the ledger can't back.
2. Draft the script → `outbox/DRAFT_lesson_<name>.md` (beats + narration + visual cues).
3. Generate the voiceover:
   - **today:** `npx hyperframes tts` (Kokoro) — pick a clear voice, note it in the script.
   - **when v0x is live:** POST narration to the Higgs endpoint (see voxx scaffold) with
     inline emotion/pace tags for a warmer teacher voice.
4. Build the visuals:
   - **Manim:** write a `Scene` per beat; render with `manim -ql scene.py` (draft) /
     `-qh` (final). Keep scenes deterministic and short.
   - **HyperFrames:** author the composition, then render to MP4.
5. Mux narration + visuals (the HyperFrames pipeline or `ffmpeg`); also export the
   **written training doc** (the script as a readable lesson) alongside the video.
6. Hand off: video + doc → `outbox/`, ledger `lesson_drafted`. The Operator reviews & airs.

## Output contract
A short narrated lesson (MP4) + a matching written training doc in `outbox/`, both honest,
both caption/readable. A draft — the Operator publishes. Pair every video with its doc so
the lesson works for readers and watchers alike.

## Failure modes
- Manim has heavy deps (LaTeX, cairo, ffmpeg) — render on a machine/POD that has them, or
  fall back to HyperFrames (browser-only). Don't block the script on the renderer.
- TTS hallucinated emphasis or wrong pronunciation → keep narration plain; spell tricky terms.
- Teaching a feature that isn't real yet → mark `[NEED: verify]`; demo only what the ledger backs.
- No music/voice you don't have rights to. Crew/real people on camera → consent rules apply 🧑.

## Refs
- Manim: https://github.com/3b1b/manim · Hermes manim skill (inspiration): nousresearch creative-manim-video
- Higgs Audio v3: https://github.com/boson-ai/higgs-audio · https://www.boson.ai/blog/higgs-audio-v3-tts
- In-repo: `framework/skills/screenwriter`, `framework/skills/video-forge`, HyperFrames TTS.
