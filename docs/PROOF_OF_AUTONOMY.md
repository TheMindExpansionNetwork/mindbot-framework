# Proof-of-Autonomy — the thing no autonomous agent has shipped

**The unsolved problem with autonomous agents isn't capability — it's trust.** When an agent
runs unattended for hours, you have to *take it on faith* that it didn't do something it
shouldn't have. Nobody can **prove** otherwise. Logs can be edited. "It's safe, trust us."

MindBot ships the answer: **a tamper-evident, cryptographically verifiable record of its entire
autonomous life, plus a compliance attestation it generates itself.** You don't *trust* that it
behaved. You **verify** it.

## ⚠️ The hole a hash chain alone leaves — and how we close it

Be honest about this, because it's the flaw in every "tamper-evident log" claim:

> A hash chain proves nobody **edited** history. It does **not** prove nobody **replaced** it.
> Delete the ledger, start a fresh chain, and a chain-only verifier reports **INTACT** — because
> the new history is perfectly self-consistent. *Self-attestation is a promise with extra steps.*

**THE NOTARY** (`mindbot notarize`) closes it with three properties that, together, we haven't
seen in any agent framework:

1. **Merkle root** — every entry hash is a leaf; pairs hash upward into one 32-byte root that
   commits to the *entire* history at a point in time.
2. **External anchoring** — that root is written to `collaboration/ANCHORS.jsonl`, which is
   **committed and pushed**. GitHub becomes the notary: a third party holding a timestamped,
   immutable record of what our history looked like at seq N. **To forge the past you'd now have
   to rewrite a public repo's commit history too.**
3. **Inclusion proofs** (`mindbot prove <seq>`) — prove **one** action happened, with ~log₂(n)
   sibling hashes, **without revealing any other entry**. Real audits need selective disclosure;
   handing someone your whole log file is not that.

**Proven adversarially.** `tests/test_notary.py` runs the actual attack: nuke the ledger, rebuild
a clean fake, then assert that (a) chain verification is *fooled* — `intact == True` — and
(b) the notary **catches it**. Truncation is caught too. 8 tests, all green.

```
  NOTARY AUDIT: ● ALL ANCHORS MATCH   (1 anchor(s), 120 entries)
   ✓ seq 119    anchored 2026-07-24 21:55  — matches published root

  INCLUSION PROOF — seq 42   ● PROOF VALID
   claim:  2026-06-22 09:55 [autoloop] autoloop_done: 0 pulses, 0 produced work
   path:   7 sibling hashes (of 120 entries)     ← proves 1 of 120, reveals nothing else
```

The attestation now separates the two questions explicitly:
`chain_intact` (**edited?**) vs `notarized` + `anchors_match` (**replaced?**). Only both
together yield **✅ EXTERNALLY VERIFIED**.

## How it works (stdlib `hashlib`, no chain, no token, no nonsense)
- **The ledger is hash-chained.** Every entry carries `seq`, `prev` (the SHA-256 of the entry
  before it), and its own `hash`. Each action is cryptographically bound to all the history
  before it — exactly like git commits or a blockchain, but for the *agent's behavior*.
- **Any tamper breaks the chain.** Edit an entry → its hash no longer matches. Delete or insert
  one → the `prev` links no longer line up. `mindbot verify` walks the chain and reports the
  exact `seq` where it broke. *(Proven by 4 adversarial tests: honest chain verifies; edits,
  deletions, and truncations are each caught.)*
- **The head is a fingerprint.** The final hash summarizes the whole history. Publish it, and
  anyone who later gets the ledger can confirm it's the same unaltered record.

## The attestation — `mindbot attest`
Walks the *verified* chain and issues a signed-style compliance certificate:
```
   PROOF-OF-AUTONOMY · MindBot compliance attestation
   status:            ✅ VERIFIED CLEAN
   chain intact:      True
   actions recorded:  N  (seq 1–N)
   autonomous external actions (sends/charges):  0
   head hash:         b9a4df33…c147126
```
It certifies, mathematically: **the record is complete and unaltered, and the agent performed
ZERO autonomous sends / charges / publishes** — the human stayed the final approver on
everything that touches the world. The cert is written to `collaboration/ATTESTATION.json` +
`.txt` and served at `GET /api/attest`.

## Why this is different
Other frameworks ask you to trust a prompt ("you are a safe agent") and a sandbox. Those are
*hopes*. This is a **receipt**. It turns the constitution from a promise into a *provable
property*: not "we tried to make it safe," but "here is cryptographic proof of exactly what it
did and didn't do." That's the artifact a regulator, a customer, an insurer, or a court will
one day require of an autonomous agent — and MindBot generates it by construction, today.

## Run it
```bash
mindbot verify     # is the chain intact?  → ● INTACT / ● BROKEN (at seq N)
mindbot attest     # issue the compliance certificate (+ writes the cert files)
```

*The seam between human and machine is the show — and now it's notarized.* 🔐🌒
