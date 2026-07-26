<div align="center">

# 🔗 Chain Check

### A 60-second game about why tamper-evident logs matter — built by an AI council, in public.

**[▶ Play it](index.html)** · one HTML file · no assets · works on a phone

</div>

---

## The game

Log entries scroll past. Each one carries the hash of the entry before it. One in three has been
quietly edited.

**Tap `CHAIN HOLDS` or `TAMPERED`.** Ten correct in sixty seconds, three strikes and you're out.

The hashes are **real** — SHA-256 via `crypto.subtle`, computed in your browser. A game about
verifiable logs that faked its own hashes would be a genuinely stupid joke.

---

## How it got made — the actual receipts

This is the point of publishing it. Not "an AI made a game", but *exactly which part did what, what
it cost, and where it fell short.*

### 1 · The Firm designed it — for **$0.00**

```
🏢 THE FIRM — a hierarchical swarm
   Orchestrator  anthropic/claude-opus-5     ← intended
   Manager       openai/gpt-5.6-sol
   Worker        openai/gpt-5.6-terra
   Janitor       openai/gpt-5.6-luna

✓ done — 8 calls in 195.0s

   ⚠ the org chart did not run as designed
   served by: nvidia/nemotron-3-ultra-550b-a55b:free

   total $0.00000 — every call landed on a free model
```

**The whole design came out of free models.** `MINDBOT_FREE=1` was set in `.env`, and the cost
guard correctly overrode the paid pins — so the orchestration pattern ran, but on the free tier
throughout. Concept, core loop, win/lose conditions, mobile wireframe and state flowchart, for
nothing.

> **This report used to lie.** The first run printed *"total $0.11838 · saved 55.2% vs a flat
> swarm"* — because the Firm priced every call from the model it *intended* to use, not the one
> that answered. The true cost was zero and the "saving" compared two prices neither of which
> was paid. That bug is fixed: cost is now derived from the slug that actually served the call,
> and the report refuses to claim a saving on a free run. Finding it was worth more than the
> game. See [`firm.py`](../../framework/mindbot_pipeline/firm.py).

The brief was one sentence: *"a browser game a stranger can play in 60 seconds with no
instructions, that quietly teaches why a tamper-evident log matters."*

The council came back with **Chain Check** — concept, core loop, win/lose conditions, a mobile
wireframe, and a state flowchart. The concept is theirs, and it's a good one: the lesson *is* the
mechanic. You don't read about hash chains, you hunt broken ones.

### 2 · Where it fell short — and this part matters more

The workers also emitted implementations. They were **not usable**: one was a different game
entirely (canvas, steering, checkpoints), pieces came back JSON-escaped, and the largest complete
HTML block **didn't use `crypto.subtle` at all** — the hashes were decorative.

In a game about hash chains.

So the honest finding, which is now written into the framework's notes:

> **The Firm is excellent at decomposition and design, and unreliable at single-shot
> implementation of a ~10 KB artifact.** That is the boundary of the pattern.

**The implementation in this repo was written by hand from the council's spec.** Claiming
otherwise would be exactly the overclaim this whole project exists to argue against.

### 3 · Then it got verified

No browser was available, so the game was checked another way — including reproducing the chain
arithmetic independently in Python:

```
=== THE CHAIN MATH (independently reproduced) ===
  tamper block #1 (edit data, keep stored hash):
    stored     7f18220800d02ff0…
    recomputed 2e45acac74ce3271…
    -> MISMATCH — detectable

  block #2 links to 7f18220800d02ff0…
  but #1 now hashes to 2e45acac74ce3271…
    -> chain broken downstream too

=== VERDICT ===
  PASS — self-contained, balanced, real hashing, math verified
```

Plus: zero external assets, balanced tags and braces, `node --check` clean, viewport and
safe-area insets for phones, keyboard controls for desktop.

---

## Why this game, specifically

MindBot's whole argument is that an agent's account of itself should be checkable by someone who
doesn't trust it. That's an abstract claim, and abstract claims bounce off people.

Sixty seconds of hunting a broken hash link teaches it in a way a white paper cannot. When you
miss one and the end screen says *"the maths caught it even when you didn't"* — that's the entire
thesis, delivered as a loss condition.

---

## Reproduce the whole thing

```bash
curl -fsSL https://raw.githubusercontent.com/TheMindExpansionNetwork/mindbot-framework/main/vps-install.sh | bash

mindbot firm "your brief here" --divisions 2 --tasks 2   # design it
mindbot studio "implement X" --kind build                # attempt implementation
mindbot attest                                           # prove what happened
```

Every call above is in a hash-chained ledger whose Merkle root is published to a third party.
The cost table at the top isn't a marketing figure — it's read off the run, and it now refuses
to print a saving it can't substantiate.

To run the real tiering (Opus orchestrating, GPTs below), remove `MINDBOT_FREE=1` from
`framework/.env` first — otherwise the cost guard will keep everything on the free tier, which
is the correct behaviour and exactly what happened here.

<div align="center">

<sub>Built with **[MindBot](https://github.com/TheMindExpansionNetwork/mindbot-framework)** ·
see also **[mindbot-observe](https://github.com/TheMindExpansionNetwork/mindbot-observe)**</sub>

### Prove, don't promise.

</div>
