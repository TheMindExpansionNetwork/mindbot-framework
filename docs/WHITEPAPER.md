# Verifiable Autonomy

### Making an AI agent's account of itself checkable by someone who doesn't trust it

**MindBot** · v0.3.0 · 2026-07-25
The Mind Expansion Network

---

## Abstract

Autonomous agents are trusted on their own testimony. An agent runs unattended, writes a log, and
reports success — but the log is a file the agent controls, so every guarantee in the stack
reduces to the agent vouching for itself. This is not a flaw in any particular framework; it is
the default architecture of the category.

We describe a system in which an agent's account of its own behaviour is **externally
verifiable**: every action is hash-chained, the chain's Merkle root is published to a third party
before the claim is read, spend ceilings are enforced *before* each model call rather than
reported after, and the code paths for sending, publishing, and charging **do not exist**. We
show that three integrity layers are required — each covering a blind spot of the one below —
and that the third, external anchoring, is the one nobody ships and the only one that closes the
loop.

We report a working implementation: 177 tests, a nightly audit across 12 platform/version
combinations, and two applications — a self-critiquing work pipeline and a multimodal
observation system that binds a model's description to the exact bytes it described.

---

## 1. The problem

Consider an agent that runs for six hours overnight. In the morning it reports success.

Did it call the model 40 times or 4,000? Did a plugin read your credentials? Did it email
someone? You have its log — a file it wrote, that it could have written differently, or not at
all. The observability story across the category is some version of *the agent writes logs, you
read the logs*. That is not an audit trail. It is an autobiography.

This matters more as agents act more independently. "What did it do while unattended?" is a
question with real stakes in regulated work, in agencies billing for agent hours, in security
review, and in incident post-mortems — and it is currently unanswerable to anyone who is not
already inclined to believe you.

## 2. Three layers, and why two are not enough

### 2.1 Hash chain

Each ledger entry binds the SHA-256 of its predecessor (`seq`, `prev`, `hash`). Edit or delete
any entry and every subsequent hash stops validating.

**Blind spot.** Delete the ledger, rebuild it from scratch, and verification reports `INTACT` —
because the forger computed those hashes too. A chain proves internal consistency, not history.

### 2.2 Merkle root

All history compresses to one 32-byte fingerprint, with RFC 6962-style inclusion proofs: ~log₂(n)
sibling hashes prove one entry belongs to the tree while revealing nothing about the others.

**Blind spot.** A fingerprint you hold locally proves nothing. You can recompute it over the
forgery.

### 2.3 External anchoring

The root is written to an append-only anchor log, committed, and **pushed to a repository you do
not control**. A third party now holds a timestamped copy that predates any later edit.

Forging history now requires producing a ledger whose Merkle root matches a value that was public
*before you started*. That is the property the first two layers cannot provide alone, and it
compounds daily: an anchor log with real history behind it cannot be backfilled.

```
ACTION ──▶ hash-chained entry ──▶ Merkle root ──▶ anchored & pushed
           tamper-EVIDENT         one fingerprint    a third party
           (edit → chain breaks)  for all history    holds it
```

**Honest limit.** Anchors are third-party evidence *only once pushed*. Before that they are a
local file the same process could rewrite, and the implementation reports them as self-attested
rather than verified. A system arguing for verifiability cannot overstate its own.

## 3. Prevention over cure: an immutable log is a hazard

Every property that makes an append-only, publicly-anchored ledger trustworthy makes a leaked
secret permanent. You cannot delete the entry (later hashes depend on it), edit it (verification
would correctly report tampering), or rewrite history (anchors would stop matching).

So redaction runs on the **write path**, unconditionally, before any entry lands.

The engineering difficulty was false positives, not detection. A naive name-based rule flagged
**22 real lines** in our own tree — `max_tokens=200`, `tokenizer=tok`,
`modal.Secret.from_name(...)`, `.env.example` placeholders. A scanner that cries wolf gets muted,
which is worse than none. Value-shape guards took it to zero without losing a detection.

Pattern *order* is load-bearing: a generic `sk-` shape swallows `sk-ant-` and `sk-or-` keys and
mislabels the provider — and the label is what tells an operator which key to rotate.

## 4. Bounded by construction

**Spend.** All model calls funnel through one chokepoint where the ceiling is checked *before*
the request leaves. An unrecognised model is priced at the most expensive rate known; an
optimistic default would let a new slug walk through a ceiling everyone believed was holding.

Precedence is a safety decision: a `MINDBOT_FREE` guard **overrides** a pinned paid model. The
failure is asymmetric — wrongly forcing a free model costs one run's quality; wrongly honouring a
paid pin in an unattended loop costs money that isn't there. A control named FREE that does not
guarantee free is worse than no control.

**External action.** There is no send, post, publish, or pay path. Not "disabled" — absent. Work
lands in an outbox; a person decides what leaves. The claim is a number readable off the ledger:
`0` autonomous external actions across ~995 recorded actions.

**Plugins.** A mod declares its capabilities; its source is walked as an AST and checked against
that declaration before it loads; undeclared calls raise `CapabilityDenied` and the *attempt* is
ledgered. A mod can lower its own spend cap, never raise it. Python cannot be fully sandboxed
in-process — this raises the cost of misbehaviour and guarantees evidence. It is not containment.

## 5. Application I: a work pipeline that criticises itself

The original loop treated every task identically — claim, pick a persona, one model call, write
markdown. A poem, a market analysis, and a Python script took the same path. That is a
persona-rotating text generator, and no better model fixes a missing loop.

The **Studio** adds typed pipelines (a `code` task plans, implements, then *executes its own
output in a subprocess*; a `build` task parses its HTML) and a **critique loop** in which a
different counselor scores the draft against explicit per-kind criteria and returns concrete
fixes.

Two findings worth recording:

**Models over-correct.** A code artifact scored 6/10, was revised against three critic notes, and
came back **4/10** — the revision broke working code while "addressing feedback". The loop now
keeps the high-water mark, not the last draft.

**Every round is ledgered.** This yields a claim we have not seen elsewhere: a tamper-evident
record of *revision history*. You can prove a piece of work was reviewed three times and show
what changed each round.

## 6. Application II: observation bound to bytes

Any model can describe an image. None can prove afterwards that it did, or that the file you hold
is the file it saw.

For each image or audio file, three hashes enter the ledger: `sha256(file bytes)`,
`sha256(observation text)`, and a chain position. Change one pixel and the file hash stops
matching; reword the description and the observation hash stops matching; rewrite history and the
anchors stop matching. Selective disclosure follows from the Merkle structure — proving one
observation while revealing nothing about the rest, which matters when the folder is evidence or
medical imaging.

Extended to video by frame sampling. The design decision that mattered:

> **A failed observation is still recorded, and never counted as a quiet one.**

An early run reported "6 quiet frames" — all clear — when every model call had died on a
transient DNS error. **An outage indistinguishable from an all-clear is the worst failure a
monitoring system can have.** Failed frames are now `UNREVIEWED`, coverage is reported, and an
incomplete run exits non-zero so a scheduled job cannot treat a partial review as a clean one.

## 7. On unreliable channels, structure beats schema

Three output formats were measured for frame classification:

1. **Sentinel phrase** — the model paraphrased it; every empty frame alarmed.
2. **Strict JSON schema** — advertised and mostly honoured, but truncated mid-object ~50% of the
   time on image inputs, returning `{\n\n\n"notable": false` with `finish_reason: "stop"`.
   Neither a larger token ceiling nor reduced reasoning effort fixed it.
3. **Line-oriented** — `NOTABLE: yes|no` on line 1.

The decisive property is **truncation behaviour**. Truncated JSON is worth nothing: lose the
closing brace and the entire payload is unparseable, including the one field you needed.
Line-oriented output degrades gracefully. On an unreliable channel, put the critical bit first
and make it independently parseable.

A related finding: reasoning tokens are spent *before* the answer. A 2048-token ceiling returned
**zero** characters of content on a code task — reasoning consumed the entire allowance. Budget
for both.

## 8. Implementation and validation

Python 3.10+, standard library only in the core: in a project whose pitch is auditability, there
is no dependency tree to audit.

- **177 unit tests.** The concurrency suite spawns real OS subprocesses because it had to: three
  concurrent writers once produced **17 duplicate sequence numbers, 3 lost entries, and a chain
  broken at seq 2**. With cross-process locking: 150/150 entries, zero duplicates, intact at six
  processes.
- **Nightly matrix**, 12 platform × version combinations. It earned its keep on the first run by
  catching a concurrency test that passed on Windows and failed on a 2-core Linux runner — the
  test asserted concurrency but never *forced* it, so it was measuring thread-startup latency.
- **Zero secrets** across 344 tracked files, enforced pre-push.

## 9. Limitations

- **Provenance is not correctness.** The system proves what happened, not that the reasoning was
  sound. It does not attempt the latter.
- **Anchors require a push** to be third-party evidence.
- **A single anchor destination is a single point of trust.** Two independent destinations would
  be strictly better and are not yet implemented.
- **Python is not a sandbox.**
- **No live-model integration test.** The machinery around the models is well covered; the models
  are not. This is the largest remaining gap.
- **No third-party security review.** The adversarial tests cover the threat model we designed
  against, which is not the threat model an attacker will use.
- **Single-machine scale.** The ledger is a local append-only file.

## 10. Conclusion

The contribution is not cryptographic novelty — hash chains, Merkle trees and inclusion proofs are
decades old. It is their application to the specific problem of **an agent's testimony about
itself**, combined with the discipline of shipping the limits alongside the claims.

A framework selling verifiability that overstates its own guarantees has refuted its pitch in the
first paragraph. Every unqualified claim here is reproducible with one command; everything else is
labelled.

> **Prove, don't promise.**

---

### Reproduce

```bash
curl -fsSL https://raw.githubusercontent.com/TheMindExpansionNetwork/mindbot-framework/main/vps-install.sh | bash
mindbot attest && mindbot verify && python framework/_full_audit.py
```

### References

- Merkle, R. (1987). *A Digital Signature Based on a Conventional Encryption Function.*
- Laurie, B., Langley, A., Kasper, E. (2013). *Certificate Transparency.* RFC 6962.
- Implementation: [`docs/PROOF_OF_AUTONOMY.md`](PROOF_OF_AUTONOMY.md),
  [`docs/TEST_REPORT.md`](TEST_REPORT.md), [`NOTES.md`](../NOTES.md)
- Demonstration: [mindbot-observe](https://github.com/TheMindExpansionNetwork/mindbot-observe)
