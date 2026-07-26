# MindBot in 5 minutes

No account. No signup. No telemetry. Runs on your machine, on models you choose, with your own
key — or free.

*This doubles as the walkthrough-video script: every step is one command with visible output.*

---

## 1 · Install (60 seconds)

```bash
git clone https://github.com/TheMindExpansionNetwork/mindbot-framework
cd mindbot-framework/framework
pip install -e .
mindbot doctor
```

Nothing else installs. The core is Python 3.10+ standard library only — there is no dependency
tree to audit, which matters in a project whose whole pitch is auditability.

## 2 · Meet it

```bash
mindbot whoami
```

It reports what it is, what it can do (read from its own live command tree), what it has done
(read from its ledger), and — unusually — **what it cannot do**. Seven limits ship in the code,
and a test fails the build if anyone trims them.

## 3 · Make something real

```bash
mindbot studio "a python script that renames photos by the date they were taken"
```

Watch what happens. It is *not* one model call:

```
  ┌─ STUDIO · CODE · Forge
  ├─ plan         769 chars
  ├─ implement   7786 chars
  ├─ critique #1  6/10  revise  → 3 fix(es)     ← a DIFFERENT counselor reviews it
  ├─ critique #2  8/10  accept       ← kept
  ├─ execute     PASS                           ← the script was actually RUN
  └─ 2026-07-25_code_rename-photos.py   6→8/10 over 2 round(s)
```

Five kinds, each with its own pipeline:

| Kind | What it does differently |
|---|---|
| `code` | plans → implements → **actually executes it in a subprocess** |
| `build` | designs → generates HTML → parses it, rejects external CDNs |
| `research` | poses its own questions first, *then* answers them |
| `decide` | lists options → commits to a recommendation and the cost of being wrong |
| `write` | drafts → critiqued for filler, unsupported claims, model-voice |

Force one with `--kind`, choose the seat with `--seat`, or pull real work off the board with
`--batch 3`.

> **Why it keeps the *best* draft, not the last one:** measured on a live run, a code artifact
> scored 6/10, was revised against three critic notes, and came back **4/10** — the revision
> broke working code while "addressing feedback". Models over-correct. The loop tracks the
> high-water mark and ships that.

## 4 · The part nobody else has

```bash
mindbot attest
```

```
  🔐 PROOF-OF-AUTONOMY
     chain           ● intact — unbroken
     merkle root     534adde10a889a75…
     anchors         11 published, all roots re-match
     standing        ● EXTERNALLY VERIFIED
     autonomous sends / posts / charges          0
```

Every action is hash-chained. The chain's fingerprint is published to a third party **before**
you read this. So "it didn't send anything while you slept" is a number you can check, not a
promise you have to take.

**That includes the critique loop.** You can prove a piece of work was reviewed three times and
show what changed each round. No other framework can show you that.

```bash
mindbot prove 224      # prove ONE action happened, revealing nothing about the others
```

## 5 · Your key, or none at all

```bash
mindbot start
```

Opens Mission Control and walks you through pasting an [OpenRouter](https://openrouter.ai/keys)
key. **You don't need one to try it** — without a key everything runs in template mode, which
produces real scaffolding and says so plainly at the top of every artifact.

On a tight budget:

```bash
echo "MINDBOT_FREE=1" >> .env      # free models only
mindbot budget                     # spend vs ceiling, always visible
```

`MINDBOT_FREE` **overrides** a pinned paid model. That precedence is deliberate: a control named
FREE that doesn't guarantee free is worse than no control at all. Ceilings are checked *before*
each call, never tallied after the invoice arrives.

---

## The 8 commands that matter

```bash
mindbot whoami       # what I am and what I can't do
mindbot board        # the task queue
mindbot studio "…"   # make something (typed pipeline + critique loop)
mindbot attest       # cryptographic standing
mindbot budget       # spend vs ceiling
mindbot review       # every draft waiting for you
mindbot scan         # secrets check before you push
mindbot mod list     # capability-scoped plugins
```

`mindbot --help` has all 65.

## Nothing leaves without you

Output lands in `framework/outbox/` and `framework/studio/`. MindBot **cannot** send an email,
publish a post, or charge a card — not "is configured not to". Those code paths do not exist.
You read the drafts; you decide what leaves.

---

**Next:** [`../NOTES.md`](../NOTES.md) how it's built and why · [`../AGENTS.md`](../AGENTS.md) if
you're pointing your own agent at it · [`THE_OFFICE.md`](THE_OFFICE.md) to run it unattended
