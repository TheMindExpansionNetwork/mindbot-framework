# Slogans — what to tell people you made

Lines for the README, the video, the badge, the reply to "so what is it?" Every one maps to
something runnable. If a line can't survive `mindbot attest`, it doesn't ship.

---

## The one

> # Prove, don't promise.

Three syllables and a comma. Names the category (proof), names the competition's whole posture
(promises), works as an instruction to the *builder* as much as the buyer, and fits under a logo.

## The line people repeat

> **Every autonomous agent tells you what it did. This one hands you the proof.**

Lead with this anywhere you have more than five words. It attacks nobody, it's checkable, and it
makes the listener notice something they already quietly knew — they've been taking their agents
at their word.

---

## By what you're pointing at

**The receipt**
- Your agent's log is a file it controls.
- Receipts, not reassurance.
- Run it overnight. Audit it at breakfast.
- Trust is a feature you can't audit.

**The critique loop** *(new — this is the differentiator most people haven't heard)*
- **Most agents show you output. This one shows you the revisions.**
- Reviewed three times. Provably.
- It grades its own work, and it can't change the grade afterwards.
- The second opinion is in the ledger.

**The budget**
- The budget is a wall, not a report.
- Checked before the call, not after the invoice.
- An unknown model is priced like the most expensive one you know.

**The human gate**
- The human holds the pen.
- It drafts. You send. There is no third option — that code path doesn't exist.

**The modding**
- Same engine, different world.
- Mod the crew, the look, the rules, the quests. Not the physics.
- A total conversion can change who the council is. It cannot switch off the ledger.

**The honesty**
- It ships a list of what it can't do, and a test that fails if you delete it.
- Not conscious. Just accountable.
- An overclaim is a defect here.

---

## Attribution — what to put on things it made

Every artifact carries its own provenance banner, and the stamp is checkable:

```bash
mindbot stamp --verify MINDBOT_STAMP.md
```

Badge:

```markdown
[![Created with MindBot](https://img.shields.io/badge/created%20with-MindBot-6E5BFF?style=for-the-badge&labelColor=0B0B14)](https://github.com/TheMindExpansionNetwork/mindbot-framework)
```

One-liners to put beside it:

- **Created with MindBot — and here's the receipt.**
- Made by an agent that kept the receipts.
- Drafted by a machine. Approved by a human. Provable either way.
- Every "Built with X" badge is an image URL. **This one is a Merkle root.**

That last one is the sharpest thing we have and it is literally true — the stamp binds to a
fingerprint published before you read it. Use it when talking to engineers.

---

## For the video

**Opening (5 seconds):** *"Your agent worked for six hours while you slept. It says it went
fine. How would you know?"*

**Middle:** run `mindbot studio` on camera. The critique loop is the moment — a **different**
counselor scores the draft 5/10, sends it back, and the run keeps the better version. That's
visible in one screen and nobody else has it.

**Close:** `mindbot attest`. Point at `autonomous sends / posts / charges: 0` and say *"that's
not a promise. Check it yourself."*

---

## Words to avoid

- **"Sentient" / "conscious" / "self-aware"** — the one claim that could never be checked, in a
  project where everything else is measured. `test_identity.py` fails the build over it.
- **"Fully autonomous"** unqualified — it drafts; a human sends. Say *"runs unattended."*
- **"Secure" / "sandboxed"** — capability scoping guarantees *evidence*, not containment.
- **"Guaranteed savings"** — the cost figure is a measured counterfactual on one run.

**Retired:** *"56% cheaper than a flat swarm."* True, measured, and the wrong hill. Any
competitor can undercut a price claim next quarter. Nobody can undercut a published Merkle root.
Keep the number as support; never as the headline.
