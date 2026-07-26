# Positioning — the slogan, and the argument underneath it

Language for the launch. Every claim here maps to something runnable; if a line can't survive
`mindbot attest`, it doesn't ship.

---

## The slogan

> # Prove, don't promise.

Three syllables and a comma, and it does four jobs at once: it names the category (proof), names
the competition's whole posture (promises), works as an imperative to the *builder* as much as to
the buyer, and is short enough to sit under a logo.

**Use it as the lockup line.** Everything below is support.

### The one-liner (the version people repeat)

> **Every autonomous agent tells you what it did. This one hands you the proof.**

This is the strongest sentence we have, and it should lead anywhere you have more than five
words. It doesn't attack anyone, it's verifiable, and it makes the listener notice something they
already quietly knew — that they've been taking agents at their word.

### The elevator paragraph

> An agent runs for six hours while you sleep and reports success. You have its word — the log it
> wrote is a file it controls. MindBot hash-chains every action, publishes a Merkle root to a
> third party before you read it, and enforces spend ceilings *before* each call rather than
> reporting them after. It cannot send, post, or charge; those code paths don't exist. You don't
> trust it. You check it.

### Alternates, by context

| Context | Line |
|---|---|
| Developer / HN | **Your agent's log is a file it controls.** |
| Enterprise / compliance | **Receipts, not reassurance.** |
| Cost-conscious | **The budget is a wall, not a report.** |
| Safety-adjacent | **The human holds the pen.** |
| The sleep test | **Run it overnight. Audit it at breakfast.** |

**Retired:** "56% cheaper than a flat swarm." It's true and measured, but leading with cost picks a
fight we win on the wrong axis — and every competitor can undercut a price claim next quarter.
Nobody can undercut a published Merkle root. Keep the number as *support*, never as the headline.

---

## Why this is actually better — the argument

Not "we have more features." One structural difference, and the features fall out of it.

### The gap everyone has

Every agent framework asks you to trust its own account of itself. The observability story is
always some version of: *the agent writes logs, you read the logs.* But the agent controls the
logs. That's not an audit trail, it's an autobiography.

This isn't a knock on any specific project — it's the default architecture of the entire category.
Which is exactly why it's a position worth taking.

### What we do instead

| | Typical framework | MindBot |
|---|---|---|
| **Action record** | app-controlled log file | hash-chained; any edit breaks the chain |
| **Integrity** | none, or a checksum you also hold | Merkle root **published to a third party** before the fact |
| **Selective disclosure** | show the whole log or nothing | prove one entry in ~log₂(n) hashes, revealing nothing else |
| **Spend control** | usage reported after the call | ceiling checked **before** the call, at one chokepoint |
| **Unknown model pricing** | assume cheap / unlisted | priced at the **most expensive** known rate |
| **Plugin trust** | trust the author | manifest of capabilities, AST-audited against it, every call ledgered |
| **External actions** | configurable guardrails | **the code paths don't exist** |
| **Stated limits** | marketing copy | 7 shipped limits with a failing test if trimmed |
| **Attribution badge** | an image URL anyone can paste | bound to a published Merkle root; forgery requires matching a public value |

### The three-layer argument (the part to actually explain)

Most people stop at layer one and think they're done. Walk them down:

1. **Hash chain** catches edits and deletions. **Its blind spot:** delete the ledger, rebuild it
   from scratch, and verification says `INTACT` — because the forger computed those hashes too.
2. **Merkle root** compresses all history to 32 bytes. **Its blind spot:** a fingerprint you keep
   locally proves nothing; you can recompute it over the forgery.
3. **External anchor** — publish the root, timestamped, somewhere you don't control. Now forging
   history means producing a ledger matching a value that was public *before you started*.

Layer three is the one nobody ships, and it's the only one that closes the loop. **That's the
moat.** Not eleven counselors, not the cost pyramid — those are good, but they're features anyone
can copy in a sprint. A published anchor log with real history behind it compounds daily and
cannot be backfilled.

### Why the honesty is a feature, not modesty

The README puts its limits on the front page: anchors aren't third-party evidence until pushed,
provenance isn't correctness, Python isn't a sandbox, spend estimates are approximate.

That reads as confidence, and it's strategically load-bearing. A framework selling verifiability
that oversells itself has refuted its own pitch in the first paragraph. Every honest limit makes
the *unqualified* claims more credible — and the unqualified ones are strong: 0 autonomous sends
across 995 recorded actions, 146 tests, 0 secrets in 280 files, every number reproducible with one
command.

**The rule:** if we can't prove it, we don't claim it. If we claim it, `mindbot attest` backs it.

---

## Objections, and honest answers

**"Isn't this just logging with extra steps?"**
Logging tells you what the app chose to record. This tells you what it recorded *and* that nothing
has been changed since — including by us. Different guarantee, not a fancier log.

**"Who actually needs cryptographic proof from an agent?"**
Anyone who has to answer "what did it do while unattended?" to someone who isn't obligated to
believe them — regulated industries, agencies billing clients for agent hours, security review,
incident post-mortems. And the number is only going up as agents get more independent.

**"Can't you just fake the whole ledger?"**
You'd need a ledger whose Merkle root matches a value already published and timestamped in a repo
you don't control. Possible if you compromise the anchor destination — which is why anchors go to
a third party and why we say plainly that anchors are only evidence *once pushed*.

**"Does this slow the agent down?"**
One SHA-256 and an fsync per action, under an OS-level file lock. Immeasurable next to a model
call.

**"Why should I believe your test numbers?"**
Don't. Run `python framework/_full_audit.py` — it prints them, and the nightly CI reruns the whole
thing across 12 platform/version combinations on GitHub's machines.

---

## Words to avoid

- **"Sentient" / "conscious" / "self-aware"** — the one claim that could never be checked, in a
  project where everything else is measured. `test_identity.py` fails the build over this.
- **"Fully autonomous"** unqualified — it drafts; a human sends. Say *"runs unattended,"* which is
  true, or *"autonomous with a human gate,"* which is the actual product.
- **"Secure" / "sandboxed"** — capability scoping guarantees *evidence*, not containment.
- **"Guaranteed savings"** — the firm's cost reporting is a measured counterfactual on one run.

See also: [`WHY_DIFFERENT.md`](WHY_DIFFERENT.md) for the six self-* properties, and
[`TEST_REPORT.md`](TEST_REPORT.md) for what the numbers do and don't establish.
