# What this actually is

*Every other doc here proves things. This one just explains it.*

---

## The short version

You get **eleven agents**. Ten are fixed. One is yours.

The ten are **lenses** — different ways of looking at a problem. You don't rename them, the same
way you don't rename a screwdriver. When someone says *"ask Quantum to check that,"* every
MindBot user on earth knows what they mean. Shared vocabulary is the point.

The eleventh is **yours**. You name it. You pick its temperament, its voice, its runner. It's the
one you actually talk to — it works out which of the ten your question belongs to, gets the
answer, and brings it back sounding like itself.

```bash
mindbot me --create --name Rook --vibe dry --pet raven
```

That's it. That's the shape.

---

## Why split it that way

A framework where **everything** is customisable has no shared language. Every install is a
different product, nobody can help anybody, and every tutorial starts with "well, depends how
you set it up."

A framework where **nothing** is customisable has no personality. It's a tool. Tools are fine.
But you don't open a tool at 2am because you're curious what it'll say.

So: **ten tools everybody shares, one character only you have.**

---

## Meet the ten

They're not employees with job titles. They're *angles*. Same question, eleven different first
sentences.

| | | asks |
|---|---|---|
| **Sage** | slow, deliberate | *"What are we actually solving?"* |
| **Forge** | builds it and runs it | *"Does it execute?"* |
| **Scribe** | writes for strangers | *"Would someone outside this room follow that?"* |
| **Vanguard** | moves first | *"What's the roughest version we could look at right now?"* |
| **Quantum** | checks the sums | *"Do these numbers add up?"* |
| **Seeker** | goes and looks | *"What do we actually know, and how do we know it?"* |
| **Spark** | says the strange thing | *"What if it were the other way round?"* |
| **Oracle** | sees, literally | *"What's in the picture?"* |
| **Titan** | carries the load | *"Who's doing the boring half?"* |
| **Tempest** | volume as strategy | *"Here's twenty. Pick one."* |
| **▸ yours** | the concierge | *"Whose question is this?"* |

Most confident plans die on Quantum. Most beautiful drafts die on Scribe. That's the value —
not that any one is smart, but that they're **different**, and the disagreement is where the
work improves.

---

## The autonomous part, honestly

People hear "autonomous agent" and picture something running loose. Here's what actually
happens.

**It works. It does not act.**

Those are different verbs and the whole design lives in the gap between them.

- It reads, thinks, drafts, writes files, runs code, reviews its own output, and files the
  result — all on its own, all night if you want.
- It **cannot** send an email, publish a post, or charge a card. Not "is configured not to."
  **Those code paths don't exist.** You can grep the whole repo. It's an absence, not a setting.

So "autonomous overnight" means: *you wake up to finished drafts in a folder*, plus a receipt
showing exactly what happened while you were asleep. Not: *you wake up to emails you didn't
write and a bill you didn't approve.*

```bash
mindbot review     # everything waiting for you
mindbot attest     # what it did, cryptographically
```

**Why the receipt matters more than it sounds.** An agent's log is a file the agent controls. It
could write anything in there — including nothing. So MindBot hash-chains every action and
publishes the fingerprint somewhere you don't control. "It didn't send anything" stops being a
promise and becomes a number you can check.

---

## Mods: it's a moddable game

The framework ships a spine. Everything interesting is a mod.

```bash
mindbot forge mod "tracks which counselor writes best"
```

That writes a complete, working mod — and here's the part that matters: a mod **declares what it
can touch**, and the runtime walks its code and enforces that declaration. Ask for a power you
didn't declare and it's refused, and the *attempt* is recorded.

Which means **you can run a mod you didn't write and still know what it did.**

### Packs are total conversions

```bash
mindbot forge pack cyberpunk-2045
mindbot forge install cyberpunk-2045
```

A pack can replace:

- **crew** — who the counselors are, their names, their voices
- **look** — palette, banner, boot sequence
- **rules** — what the critic judges against, how high the bar is
- **quests** — a campaign that seeds your board

Same engine, different world.

**What a pack can never touch:** the ledger, the budget, the human gate. Those are *engine, not
content.* A total conversion changes the world; it doesn't change physics. That rule is enforced
recursively — hiding `budget_off` three levels deep in a config file doesn't work, and there's a
test that proves it doesn't.

---

## Cheat codes

Because it should be fun to open.

```bash
mindbot cheat        # the menu
mindbot rave         # you'll see
mindbot oracle       # ask it something
mindbot trophies     # what you've actually achieved (read from the ledger)
```

The trophies aren't decorative — like everything else here, they're read from the chain. You
can't award yourself one.

---

## The pets

Every counselor has a runner. The counselor thinks; the **pet fetches**.

```bash
mindbot pets
```

```
🐢 Tortoise  Sage      █████████·····   154  companion   well fed
🐂 Anchor    Titan     ████████······     3  egg         starving
```

**A pet's level cannot be faked, because the level *is* the ledger.** A starving pet means you
genuinely haven't used that counselor. A `companion` genuinely did the work.

It's a game mechanic that's also an honest activity dashboard, and it turns out those are the
same thing if you build it from real data.

---

## What it costs

**Nothing, if you want.**

```bash
echo "MINDBOT_FREE=1" >> framework/.env
```

Free models only, hard zero. The whole "Chain Check" game — concept, mechanics, win conditions —
was designed on free models for **$0.00**.

When you do spend, the ceiling is checked **before** the call, not tallied after the invoice.
And `MINDBOT_FREE` **overrides** a paid model pin, deliberately: a control named FREE that
doesn't guarantee free is worse than no control.

---

## Where this is going

Being straight about what exists versus what's planned, because a roadmap that reads like a
feature list is how people get disappointed.

**Works today:** everything above.

**Being built:** deeper personalities (your MindBot remembering how you like to work), an
issue-to-fix pipeline (open a ticket, it drafts the patch), richer packs, more voices for a
larger council.

**Deliberately not built:** anything that sends. That's not a roadmap gap — it's the product.

---

## Five minutes from now

```bash
curl -fsSL https://raw.githubusercontent.com/TheMindExpansionNetwork/mindbot-framework/main/vps-install.sh | bash

mindbot me --create              # make yours
mindbot voices --introduce       # hear the ten
mindbot studio "something you actually need"
mindbot attest                   # the receipt
```

No account. No telemetry. Runs on your machine, on models you choose, with data that stays
yours.

---

<div align="center">

### Prove, don't promise.

<sub><a href="FIVE_MINUTES.md">the 5-minute start</a> ·
<a href="THE_BALLAD_OF_THE_ELEVEN.md">the manual, in verse</a> ·
<a href="WHITEPAPER.md">the white paper, if you want the cold version</a></sub>

</div>
