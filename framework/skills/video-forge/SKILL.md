---
name: video-forge
description: Use when the collective needs a rendered video from code — title cards, caption overlays, audio-reactive visuals, stream intros, shorts. HTML→MP4 via HyperFrames (first choice) or React→MP4 via Remotion.
status: draft
---

# video-forge

## When to use
Any task that ends in an .mp4 the council authored: stream cold-opens, lore-drop
cards, dataset-story explainers, shorts from text, DJ Nexus visualizers.

## Inputs it expects
- Node 18+ (`node -v`); a script/storyboard from the rundown or lore
- Brand palette + logo from docs/brand/ (the eclipse rides in every render)

## Steps — HyperFrames lane (HTML compositions, deterministic renders)
1. `npx hyperframes init <project>` → scaffold; compositions are plain HTML/CSS/JS
   (our 2045 rule loves this: it's just files).
2. Author the composition: brand palette, seek-driven animation (CSS/GSAP/Anime.js
   all supported), captions can sync to TTS narration (`hyperframes tts` →
   `transcribe` → caption blocks).
3. `npx hyperframes preview` → check in browser · `npx hyperframes lint` → catch
   non-determinism · `npx hyperframes render` → MP4.
4. Output to a renders/ folder; register the artifact path in the handoff; clip
   list to the content calendar's repurposing chain.

## Steps — Remotion lane (when React composition fits better)
1. `npx create-video@latest` (Remotion starter) → React components as frames.
2. `npx remotion preview` · `npx remotion render <comp> out.mp4`.
3. Same output contract as above.

## Output contract
renders/<name>.mp4 + ledger line (`video_rendered`, path, duration) + handoff entry
+ a row in the content queue. **STOP — outbox rule: rendered video is a DRAFT until
the Operator approves it for posting.**

## Failure modes
Non-deterministic animation (flagged by lint) → fix before render, never ship flaky.
Missing Node → loud [NEED: node 18+] in handoff, task re-queued. Audio without
license check → blocked; only 02_ licensed packs ride in renders.
