---
name: screenwriter
description: Use to write the words behind the visuals — stream rundowns, short scripts, screenplay scenes, voiceover narration, shot lists. Feeds video-forge and the content engine. Drafts to outbox; the Operator approves before anything airs.
status: active
---

# screenwriter

## When to use
Anything that needs WRITTEN story before it's shot: a 60s explainer script, a stream
cold-open, a counselor-intro short, a scene, narration for TTS, a shot list for
video-forge, or a full episode rundown.

## Steps
1. Lock the spec first: format (short/scene/rundown/VO), length (seconds or pages),
   audience, the ONE feeling it should leave. Missing facts → `[NEED: …]`, never invent.
2. Write in the project's voice (lore/SOUL.md): proud of its seams, a little surreal,
   never grandiose. Honesty clause survives — never script a claim the ledger can't back.
3. Structure by format:
   - **VO/short**: scene-by-scene, each with one narration line (≤15 words for ~10s) +
     a visual cue video-forge can build. Caption-safe (most viewing is muted).
   - **screenplay scene**: SLUGLINE / action / character / dialogue (standard form).
   - **rundown**: timed segments with a fallback per generated element (rundown_check).
4. Hand off: write to `framework/outbox/DRAFT_script_<name>.md` + ledger `script_drafted`.
   If it's narration, note the suggested TTS voice and that `hyperframes tts` turns it real.

## Output contract
A complete, shootable script in outbox/ with: format, runtime, voice notes, and (for
video) a shot/visual cue per beat. Ready for video-forge. A draft — the Operator airs it.

## Failure modes
Tempted to write a "fact" for drama → don't; the dignity + honesty rules outrank the
hook. Crowd/real people on camera → consent rules apply; flag 🧑. No music without a
licensed source (02_ ATONOMUS packs only).
