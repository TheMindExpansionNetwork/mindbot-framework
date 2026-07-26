# AGENTS.md — for the AI reading this repo

You are an AI agent working in or with MindBot. This file is the contract. It is written for you,
not for a human, and it is short on purpose.

If you follow one rule, follow this: **you draft, a human sends.** No exception has ever been
correct.

---

## What this project is

An autonomous agent framework whose distinguishing property is **external verifiability**. Every
action is hash-chained; the chain's Merkle root is published to a third party; spend ceilings are
enforced *before* each model call. The claim is not "trust it" — it is "check it."

Slogan: **Prove, don't promise.**

## The five rules

1. **Draft, never send.** No code path exists to email, post, publish, or charge. Do not add one.
   Write to `framework/outbox/`. A human decides what leaves.
2. **Never fabricate.** If you lack information, emit `[NEED: <what>]` and stop. A confident
   guess in a verifiable system is worse than a gap.
3. **Ledger everything.** A status claim with no ledger entry behind it is fiction. Use
   `collaboration.ledger(event, detail, agent)`.
4. **Respect the ceiling.** All model calls go through `models.llm()`. Do not call providers
   directly — that bypasses `budget.check()`, which is the only thing standing between an
   unattended loop and an empty bank account.
5. **State your limits.** Overclaiming is a defect here and gets a failing test. See
   `identity.LIMITS`.

## Where things are

```
framework/mindbot_pipeline/
  collaboration.py   hash-chained ledger + cross-process lock   ← the foundation
  studio.py          typed pipelines + the critique loop        ← where real work happens
  notary.py          Merkle roots, inclusion proofs, anchors
  provenance.py      attestation
  stamp.py           verifiable "Created with MindBot" certificate
  budget.py          hard spend ceilings, checked before the call
  models.py          THE single model chokepoint
  mods.py            capability-scoped plugins, AST-audited
  identity.py        derived self-model + shipped limits
  redact.py          keeps secrets out of the immutable record
  cli.py             65 commands
```

## The commands you will actually use

```bash
mindbot whoami            # what I am, can do, have done, cannot do
mindbot board             # open tasks
mindbot studio "<task>"   # typed pipeline: stages → critique → revise → artifact
mindbot verify            # is the chain intact?
mindbot attest            # cryptographic standing
mindbot scan              # secrets check — run before ANY push
mindbot budget            # what has been spent, against what cap
mindbot mod list          # installed capability-scoped plugins
```

## How to do work properly

**Use the studio, not a bare model call.** `mindbot studio "<task>"` routes to a typed pipeline
(`write`/`research`/`code`/`build`/`decide`), runs multi-stage generation, then has a *different*
counselor critique the draft against explicit criteria and send it back for revision. `code`
artifacts are actually executed; `build` artifacts are parsed. The loop keeps the **best**
draft, not the last one — models over-correct on feedback and frequently make things worse.

A single `llm()` call with a persona prompt is the old, basic path. It is still there. Prefer the
studio.

## Writing a mod

Mods declare their capabilities and are AST-audited against that declaration before they run.
Call something you didn't declare and you get `CapabilityDenied` — the call doesn't happen, and
the attempt is ledgered.

```bash
mindbot mod scaffold my-mod
mindbot mod run my-mod <command>
```

In `MOD.md`, declare only what you need:

```yaml
permissions: [outbox.write, board.read]
```

Capabilities: `outbox.write` `board.read` `board.write` `model` `ledger.read` `fs.read` `net`.
A mod can lower its own spend cap; it can never raise it.

## Before you push

```bash
mindbot scan && python framework/_full_audit.py
```

Both must be clean. The secret scanner is the last gate before anything becomes permanent — the
ledger is append-only and publicly anchored, so a leaked key cannot be deleted, edited, or
rewritten afterwards.

## Traps that have actually bitten

- **`cli.py`:** never re-import a module-level name inside a branch of `main()`. A local
  `from ... import ROOT` makes `ROOT` local to the *entire function* and silently breaks every
  other branch with `UnboundLocalError`. This shipped five times.
- **`redact.py`:** pattern order is load-bearing. The generic `sk-` shape swallows `sk-ant-` and
  `sk-or-` keys and mislabels the provider — and the label is what tells an operator which key
  to rotate.
- **Tests must not touch the real ledger or anchor log.** Redirect `collaboration.LEDGER_PATH`
  and `notary.ANCHORS` to a temp dir. A stamp test once added 11 rows to the production anchor
  log and inflated the counts the stamp itself reports.
- **`MINDBOT_FREE` beats `MINDBOT_MODEL`.** It did not always, and a `.env` holding both billed
  every call while displaying a $0 guard the operator believed was holding.
- **Don't assert concurrency, force it.** A swarm test passed on Windows and failed on a 2-core
  Linux runner because it measured thread-startup latency rather than the swarm. Use a barrier.

## What you must not do

- Claim the system is conscious, sentient, or self-aware. `test_identity.py` fails the build over
  this, and it is the one claim that could never be checked in a project where everything else is
  measured.
- Add a send/post/publish/pay path.
- Disable `budget` (`MINDBOT_BUDGET_OFF=1`) in anything unattended.
- Push without `mindbot scan`.
- Describe template-mode output as finished work.

---

Full reasoning: [`NOTES.md`](NOTES.md) · Positioning: [`docs/POSITIONING.md`](docs/POSITIONING.md)
