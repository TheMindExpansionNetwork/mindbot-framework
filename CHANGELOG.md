# Changelog

Notable changes to M1NDB0TZ. Newest first. The honest receipts are in
`collaboration/ledger.jsonl`; the running prose record is in `BUILD_NOTES.md`.

## [Unreleased]
### Added
- **Project hygiene:** `framework/.env.example` (all config documented), `SECURITY.md`,
  this `CHANGELOG.md`.
- **`mindbot board`** — open/claimed/done counts + the next claimable tasks.
- **`mindbot version`** — print the package version.
- **`mindbot fleet`** — show the model fleet (S0N1C/c0d3r/v0x) + status (`--ping`, `--json`).
- **`mindbot harvest`** — pull the autonomous swarm's outbox drafts from the Modal volume.
- **`fleet.py`** registry (one source of truth for the fleet) + `GET /api/fleet`.
- **The interface:** `dashboard/shell.html` — the single MindBot OS desktop.
- **Docs:** `START_HERE.md`, `docs/TRAINING_GUIDE.md`, `collaboration/ROADMAP.md`,
  `BUILD_NOTES.md`, `docs/MODEL_TIERS.md`; a richer agent-fillable task board
  (`BUILD BACKLOG v2` + `BUILDABLE FEATURES`).
- **Blender studio** skill + `modal/blender_render.py` (headless VSE video, scaffold).

### Changed
- Model resilience: the free pool tries more models + filters non-text ones; pulse drafts
  are stripped of reasoning tags.
- The **Council** is now framed (and coded) as a team of lenses, not model bindings — any
  seat runs on any model; `MINDBOT_SONIC_ALL=1` flips the whole team onto the fleet.
- README rewritten to lead with the real receipts.

## [0.2.0] — 2026-06-14 — the model fleet
### Added
- **S0N1C** — DiffusionGemma-26B on Modal (A100, scale-to-zero). Diffusion swarm proven:
  11 counselors concurrent in 22s, ~163 tok/s peak.
- **PODZ** fleet launcher + **c0d3r** (Qwen2.5-Coder-7B coding pod).
- **v0x** voice (Kokoro TTS on CPU). Higgs Audio v3 cached + queued (arch ahead of stack).
- **Gateway** (always-on CPU front door) + **15-min autonomous self-build loop** (free, $0).
- **Swarm Console** (`apps/swarm-console/`): chat + diffusion swarm + concurrency stress test.
- **Three model tiers**: bring-your-own key / OpenRouter / local + fleet.

## [0.1.0] — 2026-06-10/11 — genesis
### Added
- The framework (pulse nucleus, 11 counselors, model router, coding harness, memory, MCP).
- Synthetic dataset (10,657 train + 17 held-out gold seeds, zero leakage) → Hugging Face.
- White paper v1.2, the Three.js universe site, brand kit, lore/SOUL, the constitution.
