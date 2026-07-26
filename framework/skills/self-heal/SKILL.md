---
name: self-heal
description: Use when the test suite is red or a module won't import — diagnose, then drive the coding harness to fix it, never shipping unless tests pass green again.
status: active
---

# self-heal

## When to use
CI failed, `python -m unittest discover tests` is red, or an import broke after a change.

## Steps
1. `run_command python -m unittest discover tests` — capture the failing test + traceback.
2. Read the failing test AND the module it tests. Form ONE hypothesis for the break.
3. Hand the harness a tight task: fix exactly that, change nothing else.
4. Re-run the suite. Green → keep + ledger `self_heal: <what>`. Red → revert, write a
   handoff with the traceback, mark [NEED: human] — never ship a red suite.
5. Loop max 3 attempts; after that it's a human's call, honestly stated.

## Output contract
Either a green suite + a ledger line naming the fix, or an honest handoff with the
traceback and what was tried. Silent half-fixes are forbidden.

## Failure modes
The "fix" makes other tests fail → revert all, the suite is sacred. Flaky test →
flag it as flaky, don't paper over it.
