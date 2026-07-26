<div align="center">

# 📖 Trust, tested.

### An interactive guide to MindBot — designed by the council that built MindBot.

**[▶ Open the guide](index.html)** · one HTML file · no assets · works on a phone

</div>

---

## What it is

Four sections, each with something you can poke:

| § | Question | The widget |
|---|---|---|
| **01** | Why can't an agent's own log be trusted? | Read a confident summary, then open the **raw events** and find the timeout it didn't mention |
| **02** | What actually makes a record trustworthy? | A **live hash chain** — edit any entry, watch every hash after it break. Real SHA-256, in your browser |
| **03** | How does the work get better? | The critique loop — a second model scores the first and sends it back |
| **04** | Why isn't it all run on the best model? | The cost pyramid — one expensive model directs cheaper ones |

The 01 widget is the sharpest thing in it. The agent's summary says *"Searched 3 databases. No
conflicts found."* The raw events say database 2 timed out and **the search never completed**.
Both are true. Only one is checkable.

---

## How it was made — the real receipts

### The Firm designed it, on real models this time

```
🏢 THE FIRM — a hierarchical swarm
   Orchestrator  anthropic/claude-opus-5
   Manager       openai/gpt-5.6-sol
   Worker        openai/gpt-5.6-terra
   Janitor       openai/gpt-5.6-luna

✓ done — 11 calls in 43.1s

   RANK           CALLS       COST   SHARE
   Orchestrator       1   $0.00247    2.9%
   Manager            3   $0.00892   10.4%
   Worker             6   $0.04203   48.8%
   Janitor            1   $0.03266   37.9%

   total $0.08608   ·   same work all-on-claude-opus-5: $0.22040
   saved $0.13432 (60.9%) vs a flat swarm
```

`ran_as_designed: true` · `cost_is_real: true` · no substitutions.

**Opus was 2.9% of the bill and set the entire direction.** It read one paragraph of brief, split
it into three divisions, and never touched the page again. Six worker calls on a mid-tier model
did the volume. The cheapest model consolidated.

**Eight and a half cents.** Sixty-one percent cheaper than doing it all on Opus.

### The result was genuinely usable — unlike last time

The previous run of this same pattern, on **free** models, produced garbage: a different app
entirely, JSON-escaped fragments, and code that didn't use the crypto it was supposed to
demonstrate. See [`../chain-check`](../chain-check) for that write-up.

On the paid tier the janitor emitted **19,709 characters of complete, coherent HTML** that
passed every check on the first attempt:

```
unbalanced tags   none
external assets   NONE (self-contained)
{} () [] balance  ok
elements with id  32
dangling id refs  none      ← the JS and the HTML agreed with each other
node --check      OK
```

Zero dangling ID references across 32 elements is the number that matters. That means the script
and the markup were written to agree — the thing single-shot generation usually gets wrong.

**So the honest comparison, from two runs of the same pipeline:**

> Free tier: design good, implementation unusable.
> Paid tier (~$0.09): design good, implementation shipped as-is.

That is what the money buys. Not intelligence in the abstract — *coherence across a long
artifact.*

### What was added by hand

One thing. The council's chain demo was a **simulation** — buttons that said "tampered" without
computing anything.

A page arguing that claims should be checkable cannot have a fake demo of checking. So the
**live hash chain** in section 02 was written by hand: real `crypto.subtle` SHA-256, each entry
hashed over its own text plus the previous entry's hash. Type in any box and every hash below it
changes, because that is what actually happens.

Everything else is the council's, as generated.

---

## Reproduce it

```bash
# in framework/.env — comment these out or the cost guard keeps you on the free tier
# MINDBOT_FREE=1
# MINDBOT_MODEL=z-ai/glm-5.2

mindbot firm "your brief" --divisions 3 --tasks 2
```

That second line matters more than it looks: `MINDBOT_MODEL` pins *every* rank to one model and
silently flattens the pyramid. Both guards are correct — they just have to be off when you
actually want the tiering.

Every call is in a hash-chained ledger whose Merkle root is published to a third party:

```bash
mindbot attest && mindbot verify
```

<div align="center">

<sub>Built with **[MindBot](https://github.com/TheMindExpansionNetwork/mindbot-framework)** ·
play **[Chain Check](../chain-check)** · see **[mindbot-observe](https://github.com/TheMindExpansionNetwork/mindbot-observe)**</sub>

### Prove, don't promise.

</div>
