# Test Report

**Build:** MindBot v0.3.0 · **Date:** 2026-07-25 · **Platform:** Windows 10 Pro (19045), Python 3.11
**Reproduce:** `python framework/_full_audit.py`

Result: **20 / 20 system checks passed · 146 / 146 unit tests passed · 0 secrets across 280 tracked files.**

Every number in this document was produced by the run below, not written by hand. Where a check
is weak or a claim is unproven, it says so.

---

## 1 · Unit tests

```
Ran 146 tests in 4.6s — OK
```

| Suite | Tests | What it protects |
|---|--:|---|
| `test_redact.py` | 14 | secrets can never enter the append-only ledger |
| `test_budget.py` | 11 | spend ceilings hold at the single model chokepoint |
| `test_mods.py` | 10 | plugins cannot exceed their declared capabilities |
| `test_stamp.py` | 10 | a "Created with MindBot" stamp cannot be forged |
| `test_notary.py` | 8 | Merkle roots, inclusion proofs, anchor auditing |
| `test_identity.py` | 8 | the self-model stays derived and honest |
| `test_firm.py` | 3 | hierarchical routing and cost accounting |
| `test_concurrency.py` | 2 | the hash chain survives real concurrent processes |
| others | 80 | council, provenance, autonomy, commerce, CLI, smoke |

Two suites are worth calling out because they cost real wall-clock time and are the ones that
have actually caught bugs:

**`test_concurrency.py`** spawns real OS subprocesses that hammer the ledger simultaneously. It
exists because a probe with 3 concurrent writers once produced **17 duplicate sequence numbers,
3 lost entries, and a chain broken at seq 2**. After the cross-process lock: 150/150 entries, 0
duplicates, chain intact at 6 concurrent processes.

**`test_stamp.py`** is written adversarially — each test is an attack (edit a published field,
invent a Merkle root, rewrite history after issuing). A badge that always reads VALID is
decoration, and decoration would undercut the only claim this project makes.

---

## 2 · Proof-of-autonomy

| Check | Result |
|---|---|
| Ledger chain intact | ✅ 359 entries, unbroken |
| Externally verified | ✅ 11 anchors, all roots re-match |
| Autonomous external actions | ✅ **0** |
| Inclusion proof verifies | ✅ 9 sibling hashes of 359 |

Current Merkle root: `534adde10a889a7501648ba4db988552fda2156118a3367650a323631ae24b17`

The anchor audit is the check that matters. Chain verification alone reports INTACT on a ledger
that was deleted and rebuilt from scratch — the hashes are internally consistent because the
attacker computed them. Re-deriving the root at each *previously published* sequence is what
catches wholesale replacement:

```
✓ seq 224    anchored 2026-07-24 23:30  — matches published root
✓ seq 282    anchored 2026-07-25 00:00  — matches published root
✓ seq 304    anchored 2026-07-25 00:39  — matches published root
✓ seq 350    anchored 2026-07-25 01:03  — matches published root
```

**Honest limit:** anchors are only third-party evidence once `ANCHORS.jsonl` is committed and
pushed. Before that push they are a local file the same process could rewrite, and `attest()`
reports them as self-attested rather than externally verified.

---

## 3 · Budget governor

| Check | Result |
|---|---|
| Enforced by default | ✅ caps `{run: $2.00, day: $10.00, total: $100.00}` |
| Free models priced at zero | ✅ |
| Unknown models priced pessimistically | ✅ `$5.00 / $25.00` per Mtok |

Pricing an unfamiliar model at the *most expensive* rate we know is deliberate: an optimistic
default would let a new slug quietly blow through a ceiling that everyone believed was holding.
The check runs **before** the call, so an over-budget request is never billed.

---

## 4 · Mods (capability system)

| Check | Result |
|---|---|
| `hello-world` discovered, static audit clean | ✅ declares `outbox.write`, `board.read` |
| AST audit finds no undeclared capability | ✅ |
| Calling an undeclared capability | ✅ **denied and recorded** |

The denial test invokes `api.ask(...)` from a mod that never declared `model`. It raises
`CapabilityDenied`, the call does not happen, and the attempt lands in the ledger. A mod can
lower its own spend cap but never raise it (`min()` clamp against `DEFAULT_MOD_SPEND_CAP`).

---

## 5 · Secret redaction

| Check | Result |
|---|---|
| Catches provider key shapes | ✅ 8 providers + JWT, PEM, bearer, connection strings |
| No false positives on our own hashes | ✅ Merkle roots and git SHAs pass clean |
| Ledger write path scrubs | ✅ masked, and the redaction itself disclosed |
| Repo scan | ✅ **0 findings across 280 tracked files** |

The false-positive result is the one that took work. A naive name-based rule reported **22 hits
across this tree** — `max_tokens=200`, `tokenizer=tok`, `modal.Secret.from_name(...)`,
`.env.example` placeholders — all wrong. A scanner that cries wolf gets muted, which is worse
than having none. Value-shape guards took it to zero without losing a single real detection.

---

## 6 · Identity

| Check | Result |
|---|---|
| Capabilities introspected from the live CLI | ✅ 64 commands, 11 counselors |
| States plainly that it is not conscious | ✅ 7 shipped limits |

`capabilities()` reads the actual command tree and `history()` reads the actual ledger, so the
self-report cannot claim an ability the software does not have. `test_identity.py` pins the
limits so a future edit cannot quietly delete them.

---

## 7 · Interfaces

| Surface | Result |
|---|---|
| HTTP API | ✅ 19/19 routes return serializable JSON |
| CLI | ✅ 64 commands registered |
| `mindbot doctor` | ✅ all clear |

---

## Defects found and fixed during this pass

Both were found *by* the audit, which is the point of running one.

**1 · Test runs polluted the production anchor log.** Issuing a stamp anchors by design, so the
first `test_stamp.py` run appended 11 rows to the real `ANCHORS.jsonl` (11 → 22) and inflated the
action counts the stamp itself reports. Fixed by redirecting the ledger and anchor log to a
temporary directory for the whole module (`setUpModule`); the polluted rows were rolled back and
the stamp re-minted. Verified: a full re-run leaves the anchor count unchanged.

**2 · A concurrency test that passed on Windows and failed on Linux.** Found within minutes of
the nightly matrix running for the first time — which is the entire argument for building it.
`test_swarm_runs_concurrently_and_stops_on_rounds` mocked an instant pulse and then asserted that
more than one worker thread had been seen. With a no-op pulse, worker 1 burns through all 8
rounds and sets the stop flag before a 2-core Linux runner has scheduled workers 2–4. The
assertion was correct; the test simply never created the condition it claimed to check — it was
measuring thread-startup latency, not the swarm. Replaced the hope with a `threading.Barrier`:
every worker must arrive inside `pulse()` before any may return, so the swarm cannot satisfy it
sequentially, and a real regression now times out and fails loudly. Verified stable over 10
consecutive local runs.

**3 · Audit script crashed parsing clean scan output.** `mindbot scan` pads its output with blank
lines, so indexing line `[1]` raised `IndexError` on a *passing* scan — the audit reported FAIL
while the underlying fact was `scan_clean: true`. A checker that fails when everything is fine
trains you to ignore it. Fixed to take the first non-empty line and strip ANSI codes.

---

## What this report does not establish

- **No live-model integration run.** The council, firm, and imagery paths were exercised in
  template mode. Real OpenRouter calls cost money and were deliberately not made in this pass.
- ~~**Windows only.**~~ **Closed 2026-07-25.** The nightly matrix
  (`.github/workflows/nightly.yml`) now runs this same audit on Linux, macOS and Windows across
  Python 3.10–3.13 — 12 combinations, all green — so `fcntl.flock` is executed rather than
  assumed. Latest result: [`NIGHTLY.md`](../NIGHTLY.md).
- **Not a security audit.** No adversarial review by a third party, no dependency CVE scan, no
  fuzzing. The forgery tests cover the threat model we designed against, which is not the same as
  the threat model an attacker will use.
- **Single-machine scale.** The ledger is a local append-only file. Nothing here demonstrates
  behaviour across multiple hosts writing to shared storage.
