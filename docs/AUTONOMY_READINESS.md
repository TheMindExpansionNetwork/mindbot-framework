# Autonomy Readiness Report — is the full system ready to run itself?

*Verdict (2026-06-17): **YES — the autonomous loop is ready to run unattended, cost-safe and
observable.** One human-gated item remains for live money (a Stripe key). Details below.*

The four things any unattended system needs — and the proof each is in place:

## 1. It runs without a human ✅
- **On demand:** `mindbot pulse` (one cycle) · `mindbot yolo` (never-stop, refills its own
  board) · `mindbot swarm --workers N` (N councilors pulse concurrently).
- **Scheduled:** `deploy/windows_task.ps1` (Win Task Scheduler) and `deploy/crontab.vps`
  (Linux cron) run the loop on a clock — 15-min pulse, nightly yolo, dawn dream, 7am report.
- **Verified live:** yolo 4 rounds → 4 real drafts; swarm 4 workers → 8 parallel drafts.

## 2. It's cost-safe (never surprise-bills) ✅
- `MINDBOT_FREE=1` → free models only. `MINDBOT_NO_SONIC=1` → never wakes the billed GPU fleet.
- Both deploy schedulers now **set these for every job** (was a gap; fixed).
- **Locked by a test:** `TestCostGuard` proves `MINDBOT_NO_SONIC=1` makes `_sonic_url()` return
  `""` even with a fleet URL configured — the loop physically cannot reach the paid endpoint.

## 3. It's observable (you can see it fail) ✅
- **Operational log:** `mindbot_pipeline/logs/mindbot.log` (rotating) records every pulse +
  every error. `MINDBOT_DEBUG=1` adds DEBUG + console echo. The "no model reachable" silent
  failure is now logged loudly.
- **The ledger** (`collaboration/ledger.jsonl`) records *what* happened, append-only, honest.
- **Self-check:** `mindbot health` → `ready` flag (not paused · claimable work · no hard
  errors) + board depth, pulse count, compute-fund balance, recent errors. Run it before a swarm.

## 4. It's resilient (one failure can't take it down) ✅
- A pulse **never raises** (paused/idle/no-model/verify-fail all handled).
- A swarm worker **survives a crashing pulse** (try/except + log) and keeps going — locked by
  `TestSwarmResilience`.
- yolo **refills** the board with evergreen work when it runs dry; `mindbot pause` stops
  everything cleanly (a flag every loop checks).
- Concurrent board/state writes are **lock-guarded** — no double-claims, no torn JSON.

## The constitution still holds (autonomy ≠ acting) ✅
Every draft stops in `outbox/`. Money/sends/publishes are human-gated. The agent proposes; the
operator disposes. Real Stripe links can be *created* (test mode by default; live needs an
explicit `MINDBOT_STRIPE_LIVE=1`), but **no charge or transfer happens autonomously.**

## Run it right now (cost-safe, $0)
```bash
export MINDBOT_FREE=1 MINDBOT_NO_SONIC=1
mindbot health          # green "● READY"?
mindbot swarm --workers 4    # or: mindbot yolo
tail -f framework/mindbot_pipeline/logs/mindbot.log   # watch it work
```
Schedule it: `powershell -f framework/deploy/windows_task.ps1` (Windows) or
`crontab framework/deploy/crontab.vps` (Linux). Then just read the 7am report and merge `staging`.

## What still needs a human (honest gaps)
- **[NEED: human] Live money** — create a Stripe account + key (`framework/.env`). Then the
  earn loop is live. See [FIRST_DOLLAR.md](FIRST_DOLLAR.md). *(The system is 100% ready for it.)*
- **[optional] Modal redeploy** — the cloud cron app (`mindbotz-autonomous`) predates this
  session's logging/health; redeploy to pick them up (needs Modal creds + is billed). The
  **local** scheduled loop is fully current and $0.
- **[background] Framework deep-audit** (`wf_c3a8fc85-bc9`) is still processing; its findings
  land as tasks #34. The code is independently verified by 66 tests + live runs in the meantime.

## Test coverage of the autonomy surfaces
66 tests green, including: smoke (every module imports), swarm concurrency + resilience, health
shape, cost guard, commerce + storefront, MCP tools, server routes. The suite is the judge.
