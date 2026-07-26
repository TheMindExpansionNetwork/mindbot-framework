---
name: ledger-audit
description: Use weekly (or before any public ledger reading) — cross-checks ledger.jsonl against outbox, TODO completions, and git log; flags orphans and gaps. The book never lies, but it can forget; this catches forgetting.
status: active
---

# ledger-audit

## Steps
1. Parse `collaboration/ledger.jsonl` (skip malformed lines; count them).
2. Cross-check, four ways:
   - every `task_completed` ↔ a `- [x]` line in BIG_TODO_LIST (orphan completions?)
   - every outbox file ↔ a ledger event mentioning it (unledgered drafts?)
   - every `[NIGHT-RUN]` git commit ↔ a ledger or handoff line (silent work?)
   - money lines (`commons_hour`, gig income) sum correctly vs last audit
3. Write AUDIT_<date>.md → collaboration/audits/: clean items counted, discrepancies
   listed each with a proposed fix line — NEVER silently repair history; propose,
   the Operator approves corrections.
4. Ledger the audit itself: `ledger_audit: <n> events, <m> discrepancies`.

## Failure modes
Discrepancy in money lines → flag 🧑 URGENT, touch nothing. Audit finds nothing →
say "clean" with the counts; a short clean audit builds the trust long ones spend.
