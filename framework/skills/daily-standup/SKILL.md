---
name: daily-standup
description: Use each morning (or before a stream) to compile the council standup from REAL handoffs and the ledger — one line per active seat, status words only, no invented numbers.
status: active
---

# daily-standup

## Steps
1. Read the last ~12 handoff entries + the ledger tail since yesterday.
2. For each seat that did work, write ONE line in that seat's voice: what shipped,
   what's blocked. Status words only — any number must trace to a ledger line.
3. Lead with Sage, close with Mind (council rhythm). Seats with no activity are
   silent — don't manufacture lines.
4. Append the human-facing summary: top 3 things awaiting the Operator.
5. → outbox/STANDUP_<date>.md + ledger `standup`. This is the stream's cold-open script.

## Failure modes
Nothing happened overnight → say so in one honest line; a quiet night is data, not
a reason to invent activity. A seat's claim with no ledger backing → drop it, flag it.
