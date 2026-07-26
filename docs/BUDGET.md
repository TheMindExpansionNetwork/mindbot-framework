# BUDGET — the ceiling the agent physically cannot cross

> **Proof of a fire is not a smoke detector.**

MindBot had world-class *accountability*: every action hash-chained, Merkle-rooted, externally
anchored. We could **prove** exactly what the agent spent. We had **zero prevention** — a mod
holding the `model` capability, a `firm` run in a loop, or a swarm left running overnight could
drain an API balance, and all we'd offer afterwards was a beautifully notarized receipt for the
damage.

This is the missing half.

---

## How it works

Caps are checked **before** each call, at the one chokepoint every model call in the framework
passes through — `models.llm()`. Core, council, firm, swarm, yolo, evolve, and **third-party
mods** all route through it. There is no bypass path, by design.

### Three ceilings
| Scope | Stops |
|---|---|
| `run` | a runaway loop inside one process |
| `day` | a bad week caused by one bad night |
| `total` | lifetime — a hard wall you set once |

### Plus per-mod ceilings
Third-party code is the least-trusted spender in the system. Holding the `model` capability gets
a mod **a model, not a blank cheque** — default **$0.25/day**, and a manifest can only ever
*lower* its own ceiling (`min()` is load-bearing), never raise it.

### Safe by default
Enforcement is **opt-out** (`MINDBOT_BUDGET_OFF=1`), not opt-in. *A safety control you must
remember to enable is a control that will be missing when it matters.*

```bash
mindbot budget                 # spent / cap / remaining, per scope and per mod
MINDBOT_BUDGET_DAY=25 mindbot firm "..."      # raise a ceiling for one command
```

## What it looks like when it fires

```
$ MINDBOT_BUDGET_RUN=0.01 mindbot firm "..." --divisions 2 --tasks 1

   ⚠ 3 call(s) refused by the budget governor (not billed) — see `mindbot budget`
   total $0.00162   ·   same work all-on-claude-opus-5: $0.00689
```
…and permanently, in the chain:
```
seq 185  budget_denied  run $0.0000+$0.0178 > cap $0.01
seq 186  budget_denied  run $0.0000+$0.0215 > cap $0.01
seq 187  budget_denied  run $0.0000+$0.0108 > cap $0.01
```

**Note the degradation is graceful.** `llm()` never raises on a breach — it returns
`mode="budget"` with a `[NEED: budget]` marker, so an unattended loop keeps doing mechanical
work instead of crashing at 3am. (`ModAPI.ask()` is the exception: a mod fails *loudly*.)

## The property nobody else has: **provable spend limits**

Because every allow/deny decision is written to the same hash-chained ledger the notary anchors,
you get cryptographic evidence that an autonomous system **never exceeded a stated budget**.

That is an *auditable control*, not a config value. "Our AI can't spend more than $X/day, and
here is the proof" is a sentence a CFO can act on — and one no other agent framework can say.

## Design notes for the next agent
- **Prices** live in `PRICES` (USD per 1M tokens, matched by longest slug prefix). An unknown
  model bills at `UNKNOWN_PRICE` — deliberately pessimistic, so an unrecognised slug can never
  look free and slip past a ceiling.
- **Free models** (`:free`) cost nothing and are never gated — the $0 autonomous path always works.
- **Estimates are pre-flight and pessimistic** (assume a full-length reply); actual spend is
  recorded post-call from the real reply length.
- **Blocked calls are not billed.** `firm.report()` zeroes them and surfaces `blocked_by_budget`,
  or the run report — and the "% saved vs flat" claim — would be quietly wrong.
- **Never add a bypass.** The entire value is that there isn't one.

Tests: `tests/test_budget.py` — 11 tests, mostly refusals (a cap that reports overspending is an
invoice; a cap that prevents the call is a control), including a simulated 200-iteration runaway
that must be stopped.
