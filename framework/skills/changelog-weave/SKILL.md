---
name: changelog-weave
description: Use before a release or weekly recap — weave git log + the ledger into a human-readable CHANGELOG entry, grouped by theme, every line traceable to a commit or ledger event.
status: active
---

# changelog-weave

## Steps
1. `run_command git log --oneline` since the last tag/entry + read the ledger tail.
2. Group changes by theme (framework / skills / TUI / docs / content). Drop noise
   (typo fixes, formatting) into a single "housekeeping" line.
3. Write each entry as one plain sentence a non-coder understands, with the short
   SHA in parens. No marketing words.
4. Add a "VERIFIED" footer listing what was tested (tests green? harness run? counts).
5. → CHANGELOG.md (prepend newest) + ledger `changelog`. Doubles as the Sunday
   "the week, by the Mind" script.

## Failure modes
A commit claims something tests don't back → list it under "unverified" honestly.
Never write a changelog line for work that didn't land in git.
