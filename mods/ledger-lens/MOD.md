---
name: ledger-lens
version: 1.0.0
description: Turns the hash-chained ledger into something you can actually read — activity, streaks, what the council has really been doing.
author: The Mind Expansion Network
permissions:
  - ledger.read
  - outbox.write
---

# ledger-lens

The ledger is 1,000+ JSON lines. Nobody reads JSON lines. This mod reads them *for* you and
answers the questions you actually have: what has this thing been doing, when does it work, and
is it getting better or just getting busier?

**Zero model calls.** It declares no `model` capability, so it costs nothing and works with no
API key at all. Everything it reports is arithmetic over a file you already have.

## Commands

| Command | What it tells you |
|---|---|
| `mindbot mod run ledger-lens pulse` | activity by hour — when the council actually works |
| `mindbot mod run ledger-lens streak` | consecutive active days, longest run, quiet gaps |
| `mindbot mod run ledger-lens quality` | studio critique scores over time — is output improving? |
| `mindbot mod run ledger-lens report` | all of the above, written to the outbox |

## Why `quality` is the interesting one

The studio ledgers every critique round (`studio_critique`, `score=N/10`). That means the
framework has a **measurable, tamper-evident record of its own output quality over time** —
not vibes, not a changelog, an append-only series you cannot quietly edit after the fact.

If the average is flat, more model spend isn't the answer. If it's climbing, the critique loop
is earning its extra calls.

## Permissions & why

- `ledger.read` — the entire point.
- `outbox.write` — so `report` can leave something a human reads.

Deliberately **not** requested: `model`, `net`, `fs.write`, `board.write`. The static audit
refuses this mod if its code reaches for any of them, so "zero model calls" is enforced rather
than promised.
