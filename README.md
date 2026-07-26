<div align="center">

<img src="assets/banner.svg" alt="MindBot — the agent you can prove" width="100%">

<br>

**Every autonomous agent tells you what it did.**
### **This one hands you the proof.**

<br>

[![Created with MindBot](https://img.shields.io/badge/created%20with-MindBot-6E5BFF?style=for-the-badge&labelColor=0B0B14)](MINDBOT_STAMP.md)
[![Tests](https://img.shields.io/badge/tests-146%20passing-32E6A0?style=for-the-badge&labelColor=0B0B14)](docs/TEST_REPORT.md)
[![Autonomous sends](https://img.shields.io/badge/autonomous%20sends-0-32E6A0?style=for-the-badge&labelColor=0B0B14)](#the-human-holds-the-pen)
[![Python](https://img.shields.io/badge/python-3.10+-6E5BFF?style=for-the-badge&labelColor=0B0B14)](framework/pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-8F88C4?style=for-the-badge&labelColor=0B0B14)](LICENSE)

<br>

**[Quickstart](#quickstart)** · **[Why it's different](#why-this-is-different)** · **[The proof](#the-proof)** · **[Mission](MISSION.md)** · **[Test report](docs/TEST_REPORT.md)**

</div>

<br>

---

<br>

## The problem

An agent runs for six hours while you sleep. In the morning it reports success.

You have its word. That's it.

Did it call the model 40 times or 4,000? Did that "harmless" plugin read your keys? Did it email
someone? The log it wrote is a file it controls — it could have written anything, including
nothing. Every guarantee in that stack is the agent vouching for itself.

**MindBot replaces the agent's word with evidence a stranger can check.**

<br>

```
  ACTION ──▶ hash-chained entry ──▶ Merkle root ──▶ anchored & pushed ──▶ third party holds it
             tamper-EVIDENT          one fingerprint    timestamped         you can't rewrite
             (edit → chain breaks)   for all history    before the fact      the past
```

Three layers, each covering the blind spot of the one below:

| Layer | Catches | Blind spot it has alone |
|---|---|---|
| **Hash chain** | any edit or deletion | a ledger deleted and rebuilt from scratch verifies clean |
| **Merkle root** | all of history, in one 32-byte fingerprint | a fingerprint you keep locally proves nothing |
| **External anchor** | wholesale replacement | — |

The third layer is the one that matters and the one nobody ships. Chain verification alone
reports `INTACT` on a forged ledger, because the forger computed those hashes too. Re-deriving
the root at a sequence number **published before the forgery** is what makes lying expensive.

<br>

---

<br>

## Quickstart

```bash
git clone https://github.com/TheMindExpansionNetwork/mindbot-framework
cd mindbot-framework/framework
pip install -e .
mindbot start
```

That's it. `mindbot start` opens Mission Control, walks you through pasting **your own**
OpenRouter key, and runs entirely on your machine. No account, no telemetry, no hosted anything.
The core is Python 3.10+ standard library — there is no dependency tree to audit.

<details>
<summary><b>Prefer the terminal?</b></summary>

<br>

```bash
mindbot whoami          # what I am, what I can do, what I've done, what I can't
mindbot doctor          # is this environment sane?
mindbot verify          # is my history unbroken?
mindbot attest          # print a compliance certificate
mindbot notarize        # publish a Merkle root; commit + push to notarize it
mindbot prove 224       # prove ONE action happened, without revealing the rest
mindbot budget          # what have I spent, against what ceiling?
mindbot scan            # any secrets in tracked files before I push?
mindbot stamp           # mint a verifiable "Created with MindBot" certificate
mindbot firm "<goal>"   # hierarchical swarm down a cost pyramid
```

64 commands total — `mindbot --help`.
</details>

<br>

---

<br>

## Why this is different

### The human holds the pen

MindBot **cannot** send an email, publish a post, or charge a card. Not "is configured not to" —
**those code paths do not exist.** It drafts to an outbox; a person sends.

This is the claim agent frameworks make loudest and prove least. Ours is a number you can read
off the ledger, and it is currently `0` across **995 recorded actions since 2026-06-11**.

### The budget is a wall, not a report

Every model call funnels through one function, and the ceiling is checked **before** the request
leaves — not tallied after the invoice arrives.

```python
try:
    budget.check(model, len(system) + len(prompt))
except budget.BudgetExceeded as e:
    return f"[NEED: budget] {e}", "budget"      # the call never happens
```

An unrecognised model is priced at the **most expensive rate we know** ($5/$25 per Mtok). An
optimistic default would let a new slug quietly walk through a ceiling everyone believed was
holding.

### Plugins declare their powers — and the code is audited against the declaration

A mod ships a manifest of capabilities. Before it runs, its source is walked as an AST and checked
against what it declared. Call something you didn't declare and you get `CapabilityDenied`: the
call doesn't happen, and the *attempt* goes into the ledger.

A mod can lower its own spend cap. It cannot raise it.

### It says what it can't do

`mindbot whoami` ships seven limits, and `test_identity.py` fails the build if they're trimmed:

> *I am not conscious, sentient, or self-aware in the human sense. I am software that can
> accurately report its own state.*
>
> *I cannot verify that my own model's reasoning is correct. My guarantees are about what I DID
> (recorded, provable), not about whether my judgment was good.*
>
> *My mods are audited and capability-scoped, but Python cannot be fully sandboxed in-process. A
> determined mod can evade static analysis — it just cannot act without leaving evidence.*

An overclaim is treated as a defect, and it gets a failing test.

<br>

---

<br>

## The proof

Anyone can run this against a MindBot repo — including this one.

```console
$ mindbot attest

  🔐 PROOF-OF-AUTONOMY
     chain           ● intact — 359 entries, unbroken
     merkle root     534adde10a889a7501648ba4db988552fda2156118a3367650a323631ae24b17
     anchors         11 published, all roots re-match
     standing        ● EXTERNALLY VERIFIED
     autonomous sends / posts / charges          0
```

**Prove one action without revealing the rest.** Selective disclosure, RFC 6962-style: hand an
auditor ~log₂(n) sibling hashes and they can confirm entry #224 belongs to a published history —
while learning nothing about entries 1–223.

```bash
mindbot prove 224
```

→ [How proof-of-autonomy works](docs/PROOF_OF_AUTONOMY.md)

<br>

---

<br>

## The stamp

Every "Built with X" badge on GitHub is an image URL. Anyone can paste one anywhere. It asserts
nothing, which is why nobody trusts them.

Ours is bound to the ledger that recorded the work:

```
stamp_id = sha256( project | merkle_root | seq | issued )[:16]
```

Because issuing a stamp **anchors first**, the root it cites is already published by the time the
stamp is written. To forge one you would have to produce a ledger whose Merkle root matches a
value that was public before you started.

```bash
mindbot stamp --verify MINDBOT_STAMP.md
```

```console
  🏷️  STAMP  ● VALID   MINDBOT_STAMP.md
   ✓ id matches          the fields hash to the id — nothing was edited
   ✓ root published      that root is in the anchor log — it wasn't invented
   ✓ chain intact        history hasn't changed since — no rewrite
```

**A stamp is a chain of custody, not a seal of approval.** It says the work's provenance is
intact. It says nothing about whether the work is any good.
→ [`MINDBOT_STAMP.md`](MINDBOT_STAMP.md)

<br>

---

<br>

## The council

Eleven counselors — **lenses, not model bindings.** Each is a distinct way of interrogating a
problem, and any of them can run on any model you point it at.

<div align="center">

`Sage` · `Forge` · `Scribe` · `Vanguard` · `Quantum` · `Seeker` · `Spark` · `Oracle` · `Titan` · `Tempest` · `Mind`

</div>

For heavier work, **The Firm** routes hierarchically down a cost pyramid — an orchestrator plans,
managers decompose, workers execute in parallel, a janitor consolidates. Each rank runs on a
cheaper tier than the one above it, and `mindbot firm` reports the flat-swarm counterfactual so
the saving is measured rather than claimed.
→ [`docs/CASE_STUDY_THE_FIRM.md`](docs/CASE_STUDY_THE_FIRM.md)

<br>

---

<br>

## Verified state

> Measured 2026-07-25 by `python framework/_full_audit.py`. Full breakdown — including what it
> does **not** establish — in **[docs/TEST_REPORT.md](docs/TEST_REPORT.md)**.

<div align="center">

| | | | |
|:--:|:--:|:--:|:--:|
| **20 / 20** | **146** | **0** | **0** |
| system checks | unit tests | autonomous sends | secrets in 280 files |
| **995** | **11** | **64** | **stdlib** |
| recorded actions | published anchors | CLI commands | only, in the core |

</div>

The concurrency suite spawns real OS subprocesses, because it had to. A probe with three
concurrent writers once produced **17 duplicate sequence numbers, 3 lost entries, and a chain
broken at seq 2**. With cross-process locking: 150/150 entries, zero duplicates, intact at six
processes. That test is now permanent.

And it runs everywhere, nightly:

[![night shift](https://img.shields.io/github/actions/workflow/status/TheMindExpansionNetwork/mindbot-framework/nightly.yml?style=for-the-badge&label=night%20shift&labelColor=0B0B14&color=32E6A0)](../../actions/workflows/nightly.yml)

**12 / 12** platform × version combinations — Linux, macOS and Windows on Python 3.10–3.13 —
run the full audit every night on GitHub's machines and write [`NIGHTLY.md`](NIGHTLY.md). It
costs nothing by construction: no API key is present, so every model path degrades to template
mode. A nightly job that quietly bills you is a nightly job you turn off.

Its first run earned its keep immediately. A concurrency test that had always passed on Windows
**failed on a 2-core Linux runner** — with an instant mocked pulse, worker 1 burned through every
round before the OS had scheduled workers 2–4, so the test was measuring thread-startup latency
rather than the swarm. It now forces overlap with a barrier.

<br>

---

<br>

## Honest limits

Load-bearing, so they go on the front page rather than in a footnote:

- **Anchors are only third-party evidence once pushed.** Before that they are a local file the
  same process could rewrite — and `attest()` reports them as self-attested, not verified.
- **Provenance ≠ correctness.** MindBot proves what happened. It cannot prove the reasoning was
  sound, and it does not try to.
- **Python isn't a sandbox.** Capability scoping raises the cost of misbehaviour and guarantees
  evidence. It is not containment. Untrusted mods belong in a container.
- **Spend estimates are approximate** (~4 chars/token) and enforced pessimistically. A hard
  ceiling built on an estimate is a tight bound, not an exact one.
- **No live-model integration test.** Everything above is exercised in template mode. The
  machinery *around* the models is well covered; the models are not. This is the biggest
  remaining hole.

<br>

---

<br>

<div align="center">

### Prove, don't promise.

<sub>MIT licensed · runs on hardware you control · models you choose · data that stays yours</sub>

<br>

[![Created with MindBot](https://img.shields.io/badge/created%20with-MindBot-6E5BFF?style=for-the-badge&labelColor=0B0B14)](MINDBOT_STAMP.md)

<sub>This README was written by the agent it describes.<br>
The stamp above covers the run that produced it — <code>mindbot stamp --verify MINDBOT_STAMP.md</code></sub>

</div>
