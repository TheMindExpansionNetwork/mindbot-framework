---
name: blender-studio
description: Use to drive Blender headlessly for video editing (VSE), 3D scenes, and programmatic rendering via Python — turning scripts/specs into real MP4s and visuals. The heavy creative engine behind films, instructional videos, and motion graphics. Renders to outbox; the Operator publishes.
status: draft
---

# blender-studio

## When to use
Anything that needs real rendered video or 3D that HTML/HyperFrames can't do: cutting and
sequencing clips (the **VSE** — Video Sequence Editor), title/animation scenes, 3D text,
compositing, batch rendering. Blender is fully scriptable and runs **headless**, so an
agent can build and render video from a Python script with no GUI.

## Why Blender (the capabilities)
- **`bpy`** — Blender's Python API. Every part of the app is programmable: scenes, cameras,
  keyframes, the VSE timeline, render settings.
- **Headless CLI:** `blender --background --python script.py` runs with no display — on a
  server, in CI, or on a Modal GPU/CPU container. Perfect for agents.
- **VSE** — load clips/audio/images onto a timeline, cut, cross-fade, overlay text, export MP4.
- **Render** — Eevee (fast) or Cycles (photoreal); set resolution/fps/codec in script.

## Steps
1. Lock the spec (use `screenwriter` / `instructional-video` first): scenes, durations,
   text, clips, audio, output (res/fps). Missing facts → `[NEED: …]`, never invent.
2. Write a `bpy` script. Skeleton for a VSE edit:
   ```python
   import bpy
   scene = bpy.context.scene
   scene.sequence_editor_create()
   se = scene.sequence_editor
   se.sequences.new_movie("clip1", "/in/clip1.mp4", channel=1, frame_start=1)
   se.sequences.new_sound("vo", "/in/narration.wav", channel=2, frame_start=1)
   # text overlay
   t = se.sequences.new_effect("title", type='TEXT', channel=3, frame_start=1, frame_end=120)
   t.text = "M1NDB0TZ"; t.font_size = 96
   scene.render.image_settings.file_format = 'FFMPEG'
   scene.render.ffmpeg.format = 'MPEG4'; scene.render.fps = 30
   scene.render.filepath = "/out/lesson.mp4"
   bpy.ops.render.render(animation=True)
   ```
3. Render it:
   - **Local:** `blender --background --python edit.py` (needs Blender installed).
   - **Headless on Modal:** `modal run modal/blender_render.py` — a container with Blender,
     inputs from a Volume, MP4 back out. (See that file; pip `bpy` or the Blender CLI image.)
4. Hand off: MP4 (+ the script that made it, for reproducibility) → `outbox/`, ledger
   `video_rendered`. The Operator reviews & publishes.

## Pairs with
- `instructional-video` (script + narration → Blender renders it) · `screenwriter` (the words)
- `v0x` voice (`modal/voxx_kokoro_tts.py`) for the narration track
- HyperFrames for quick HTML→MP4 when full Blender is overkill

## Output contract
A rendered MP4 in `outbox/` + the reproducible `bpy` script beside it. Deterministic
(seeded, fixed fps/res) so a re-render matches. A draft — the Operator airs it.

## Failure modes
- Blender has heavy deps (the binary, ffmpeg, optional CUDA). Render on a machine/POD that
  has them; don't block the script on the renderer being absent.
- `bpy` as a pip wheel exists but is version-touchy — prefer the official Blender CLI image
  for headless on Modal; fall back to HyperFrames if Blender isn't available.
- Cycles + GPU is slow/expensive — default to Eevee for drafts; Cycles only for finals.
- Never render copyrighted footage/music you don't have rights to. Real people → consent 🧑.

## Refs
- Programmatic rendering: https://blog.cg-wire.com/blender-programmatic-rendering/
- Scripting for pipelines: https://blog.cg-wire.com/blender-scripting-animation/
- Headless helper: https://github.com/oqton/blenderless · CLI guide: https://renderday.com/blog/mastering-the-blender-cli
- AI automation incl. VSE: https://github.com/sandraschi/blender-mcp
