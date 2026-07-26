# The Office — the framework working its own board while your machine is off

**Status: drafted, not installed.** This is the design and the exact workflow file. Installing it
is a deliberate act, and it should be — a scheduled job that commits to your repo unattended,
forever, is not something to switch on by accident.

That's the same gate the framework applies to itself. The agent drafts; a human commits.

---

## What it is

Every 6 hours, on GitHub's machines, with your computer off:

1. **Clocks in** — `whoami`, `verify` the chain, read the `board`
2. **Works the board** — `autopilot` claims tasks and drafts, N councilors in parallel
3. **Refills the board** — `reflect --propose 3`, so it doesn't empty its queue and idle forever
4. **Summarizes** — `digest`, `budget`, `review`
5. **Notarizes** — anchors the Merkle root covering that shift
6. **Scans for secrets** — the last gate before anything leaves
7. **Files the paperwork** — commits drafts, board, ledger and anchor back to `main`

You wake up to a shift's work in `framework/outbox/`, and a ledger entry for every step.

## What it does *not* do

**Nothing changes about the constitution.** It cannot: the send / post / publish / charge code
paths do not exist. "Unattended" here means unattended **drafting**. Running in CI changes where
the work happens, not what it's allowed to do — which is precisely why it's safe to leave
running, and why this is worth doing at all.

## What it costs

**$0 by default.** With no `OPENROUTER_API_KEY` repo secret, every model call degrades to
template mode: the loop still runs, claims tasks, and produces scaffolded drafts — real
structure, no real thinking.

To give it a mind you add the secret yourself (below). Then these caps apply, and they're all
opt-**out**, because an unattended loop that can silently spend is the most dangerous thing in
this repo:

| Guard | Value | Why |
|---|---|---|
| `MINDBOT_BUDGET_RUN` | `$0.25` | per-shift ceiling, checked *before* each call |
| `MINDBOT_BUDGET_DAY` | `$1.00` | four shifts a day cannot exceed a dollar |
| `MINDBOT_BUDGET_TOTAL` | `$20.00` | lifetime backstop |
| `MINDBOT_FREE` | on | free models only, unless a human ticks "paid" on a manual run |
| `MINDBOT_NO_SONIC` | on | never wakes the billed GPU fleet |

**A scheduled run can never opt into paid models.** That decision requires a person ticking a box
on a manual dispatch, every single time.

---

## Before you install it — three things I'd want you to know

1. **Your key is compromised.** `sk-or-v1-8035…` was pasted into a chat. Rotate it *before* it
   goes anywhere near a repo secret.
2. **You said you have about $5.** With free models pinned this stays at $0, but if you ever tick
   "paid", four shifts a day against a $1/day cap drains it in five days. The cap protects you
   from a runaway loop, not from steady intended spend.
3. **Template mode is not a failure mode, it's the honest default.** A free-model office produces
   real scaffolding and real ledger history. Read a few shifts' drafts before deciding it's worth
   money.

## Installing it

Rotate your key first. Then:

```bash
gh secret set OPENROUTER_API_KEY --repo TheMindExpansionNetwork/mindbot-framework
```

That prompts you to paste it — the value goes straight from your terminal to GitHub, and I never
see it. **Skip this step entirely to run the office for free in template mode.**

Then save the file below as `.github/workflows/office.yml`, commit, and push:

```bash
git add .github/workflows/office.yml
git commit -m "install: the office"
git push
```

Run it once by hand before trusting the schedule:

```bash
gh workflow run "the office" --repo TheMindExpansionNetwork/mindbot-framework
```

To stop it at any time: `gh workflow disable "the office" --repo TheMindExpansionNetwork/mindbot-framework`

> **GitHub disables scheduled workflows after 60 days of repo inactivity.** The office commits on
> every shift, so it keeps itself alive — but if you ever pause it, re-enable it manually.

---

## The workflow file

```yaml
name: the office

# The framework working its own board, on GitHub's machines, with your computer switched off.
# Every output lands in framework/outbox/ and waits for a human. See docs/THE_OFFICE.md.

on:
  schedule:
    - cron: "0 */6 * * *"       # every 6 hours
  workflow_dispatch:
    inputs:
      rounds:
        description: "pulses across the swarm"
        default: "6"
      workers:
        description: "concurrent councilors"
        default: "3"
      paid:
        description: "allow paid models (requires the secret; still budget-capped)"
        type: boolean
        default: false

# One office at a time. Two concurrent shifts would claim from the same board and race each
# other's commits — the ledger lock protects the chain, not your git history.
concurrency:
  group: the-office
  cancel-in-progress: false

permissions:
  contents: write

env:
  PYTHONUTF8: "1"
  PYTHONIOENCODING: "utf-8"
  MINDBOT_NO_SONIC: "1"         # never wake the billed GPU fleet from an unattended loop
  MINDBOT_BUDGET_RUN: "0.25"
  MINDBOT_BUDGET_DAY: "1.00"
  MINDBOT_BUDGET_TOTAL: "20.00"

jobs:
  work:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: main
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }

      - name: Install
        working-directory: framework
        run: pip install -e .

      - name: Clock in — who am I, and am I within my rules?
        working-directory: framework
        run: |
          python -m mindbot_pipeline.cli whoami
          python -m mindbot_pipeline.cli verify
          python -m mindbot_pipeline.cli board

      - name: Work the board
        working-directory: framework
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
          # Free models unless a human explicitly ticked "paid" on a MANUAL run. A scheduled
          # run can never opt into paid models — that decision requires a person, every time.
          MINDBOT_FREE: ${{ (github.event_name == 'workflow_dispatch' && inputs.paid == true) && '' || '1' }}
        run: |
          python -m mindbot_pipeline.cli autopilot \
            --rounds  "${{ inputs.rounds  || 6 }}" \
            --workers "${{ inputs.workers || 3 }}"

      - name: Refill the board — propose the next tasks
        working-directory: framework
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
          MINDBOT_FREE: ${{ (github.event_name == 'workflow_dispatch' && inputs.paid == true) && '' || '1' }}
        # Without this the office empties its board and idles forever. Self-direction is what
        # makes it a standing operation rather than a one-shot script.
        run: python -m mindbot_pipeline.cli reflect --propose 3 || echo "reflect degraded — board unchanged"

      - name: Summarize the shift
        working-directory: framework
        run: |
          python -m mindbot_pipeline.cli digest || true
          python -m mindbot_pipeline.cli budget
          python -m mindbot_pipeline.cli review || true

      - name: Notarize the shift
        working-directory: framework
        # Anchor BEFORE committing, so the root published in this commit covers the work in it.
        run: python -m mindbot_pipeline.cli notarize --note "office shift"

      - name: Secret scan — the last gate before anything leaves
        working-directory: framework
        run: python -m mindbot_pipeline.cli scan

      - name: File the paperwork
        run: |
          git config user.name  "mindbot[the-office]"
          git config user.email "noreply@github.com"
          git add -A
          git diff --staged --quiet && { echo "quiet shift — nothing to file"; exit 0; }
          git commit -m "office: shift complete — drafts, board, ledger, anchor"
          # Rebase before pushing: the night shift commits to this branch too, and losing a
          # shift's drafts to a non-fast-forward is worse than a slightly noisy history.
          git pull --rebase --strategy-option=theirs origin main || true
          git push

      - name: Attest what the shift did
        if: always()
        working-directory: framework
        run: python -m mindbot_pipeline.cli attest
```

---

## Reading the shift in the morning

```bash
git pull
mindbot review          # every draft the office produced
mindbot board           # what it claimed, what's still open
mindbot budget          # what it spent (0.0000 in template mode)
mindbot attest          # the shift, cryptographically
```

Every draft is a file. Nothing was sent. That's the point.
