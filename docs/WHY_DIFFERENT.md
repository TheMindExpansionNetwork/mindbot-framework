# Why MindBot is different — the six self-* properties

Most agent frameworks are a loop that calls a model and runs tools. MindBot is built around one
idea other frameworks don't chase: **an agent collective that runs, funds, improves, and directs
itself — safely.** Six properties, each a real command you can run today, not a slide:

| # | Property | What it means | Run it |
|---|----------|---------------|--------|
| 1 | **Self-running** | claims work and produces drafts with no human in the loop | `mindbot yolo` / `mindbot autopilot` |
| 2 | **Self-organizing** | many councilors work the board *concurrently*; refills itself when dry | `mindbot swarm --workers 11` |
| 3 | **Self-improving** | writes + **tests** + proposes its OWN code; red tests auto-revert | `mindbot evolve` |
| 4 | **Self-directing** | reviews what it's done and proposes its next high-leverage goals | `mindbot reflect` |
| 5 | **Self-funding** | earns via Stripe → pays for its own NVIDIA compute (the flywheel) | `mindbot commerce` |
| 6 | **Self-monitoring** | a readiness self-check + an operational log + trophies from real progress | `mindbot health` / `mindbot trophies` |

## The one that almost no one does: self-improving (#3)
Other frameworks draft *text* for a human to implement. MindBot runs a **jailed coding harness**
where **tests are the judge**: it writes real code, runs the real suite, and **keeps the change
only if it stays green** (red → auto-revert). Then it drafts the verified diff to the outbox for
a human to commit. *It doesn't tell you what to build — it builds it, proves it, and asks you to
merge.* Even a weak free model attempting this **cannot break the repo** — the test gate + revert
guarantee it. (Verified live: a free-model run failed honestly and left zero trace.)

## What keeps all six SAFE — the constitution
Autonomy here is a *direction*, not a blank check. The safety is in the plumbing, not promises:
- **Agent drafts, human sends.** Every external action (money, posts, publishes, merges to
  `main`) stops at the outbox / a human gate. Nothing transmits or charges on its own.
- **Tests are the judge.** No red build is ever kept.
- **Cost-safe by default.** Unattended loops force free models + `MINDBOT_NO_SONIC` — they
  *physically cannot* reach the billed GPU fleet (locked by a test).
- **The ledger never lies.** Append-only; a status claim without a ledger line is fiction.

## The result
An eleven-seat council you can `pip install`, point at a folder, and walk away from — it works
tasks, improves its own code, proposes its next moves, funds its own compute, and leaves an
honest trail — while a human stays the final approver on anything that touches the world. It also
runs **as a Hermes skill pack** and over **MCP**, so any agent ecosystem can drive it.

*The seam between human and machine is the show — and the safeguard.* 🌒
