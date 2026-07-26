---
name: skill-name-kebab-case
description: One sentence: what this skill does and WHEN an agent should reach for it. This line is the trigger — write it for the router, not the reader.
---

# Skill Name

## When to use
Concrete trigger conditions. An agent skimming 50 skills must know in one line.

## Inputs it expects
Paths, env vars, state it reads. Mark anything uncertain [NEED: ...].

## Steps
1. Numbered, mechanical, reproducible. Another model on another night must get the
   same result.
2. Every step that writes: say WHERE. Every step that could transmit: say
   **STOP — outbox, human sends.**

## Output contract
What exists after a successful run (files, ledger lines, handoff entry).

## Failure modes
What goes wrong and what the loud failure looks like. Silent failure is forbidden.

---
*Format note: this frontmatter (name + description) is the same contract used by
Claude Code skills and Hermes SKILL.md — keep it, and any marketplace that speaks
SKILL.md can load council skills unchanged. Skills dreamed by the dream_cycle land
here as drafts with `status: dreamed` until a counselor test-runs them.*
