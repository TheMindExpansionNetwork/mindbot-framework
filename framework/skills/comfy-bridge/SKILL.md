---
name: comfy-bridge
description: Use when a task needs image/video generation through a local ComfyUI instance — character keepers (h34dsh0t conventions), stream overlays, dream-canvas visuals. Queues workflows via the ComfyUI HTTP API; renders are drafts until the Operator keeps them.
status: draft
---

# comfy-bridge

## When to use
Any render task: Lorekeeper/DJ Nexus keeper batches, MindBot canonical face work,
lore illustrations, audio-reactive stream visuals. Ancestor: MINDBOT_HQ
`artmind.py` plugin (ComfyUI workflows + brain-state params).

## Inputs it expects
- ComfyUI running locally (default `http://127.0.0.1:8188`); env `COMFYUI_HOST` to override
- A workflow JSON (API format: ComfyUI → dev mode → "Save (API Format)") in `workflows/`
- Identity blocks from `lore/CHARACTER_MANIFEST.json` — LOCKED text goes in verbatim

## Steps
1. Health check: `GET /system_stats` — if down, loud [NEED: start ComfyUI], re-queue.
2. Load workflow JSON; inject prompt = identity block + ONE variation-axis value;
   set seed explicitly (deterministic — log the seed; never random-and-forget).
3. `POST /prompt` with the graph; poll `GET /history/{prompt_id}` until done.
4. Collect outputs via `GET /view?filename=...` → save to `renders/comfy/<batch>/`.
5. Batch-8: repeat with 8 logged seeds. **The Operator keeps 2** — taste stays human.
6. Keeper IDs + prompt hash + seeds → CHARACTER_MANIFEST.json; batch → ledger + trails.

## Output contract
renders/comfy/<batch>/ images + manifest rows + ledger line (`comfy_batch`, count,
seeds). Keepers are drafts for the manifest until the Operator picks.

## Failure modes
ComfyUI unreachable → [NEED] + re-queue, never fake. Identity-block edit attempted →
refuse; locked blocks change only by council decision. VRAM OOM → halve batch, note it.
