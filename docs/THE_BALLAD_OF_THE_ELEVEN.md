# The Ballad of the Eleven

### An instruction manual that rhymes

*Read it. Or better — let it read itself to you:*

```bash
mindbot say --file docs/THE_BALLAD_OF_THE_ELEVEN.md --as Scribe --out ballad.wav
```

---

## I. The Complaint

> Every agent tells you it did well.
> Every agent writes its own report.
> The log is a file the agent controls —
> so the log is a story, not a court.
>
> It ran six hours while you slept.
> It says it went fine. It says it was quick.
> You have its word, and only its word,
> and its word is a very convenient trick.

**So we built one that hands you the proof instead.**

```bash
mindbot attest
```

---

## II. The Three Locks

> **The first lock is the chain.**
> Each entry holds the one before,
> so an edit anywhere in the middle
> breaks every hash from there to the door.
> *But delete it all and build it new —
> and the chain says INTACT, because the forger hashed it too.*
>
> **The second lock is the root.**
> A thousand actions, thirty-two bytes,
> and a proof that one belongs to the whole
> without ever showing the rest to your sight.
> *But a root in your pocket proves nothing at all.
> You can recompute it over the lie.*
>
> **The third lock is the one nobody ships.**
> Publish the root where you don't hold the key.
> Now forging the past means matching a number
> that was public before you began. **That's the moat.** That's the whole of it. That's why.

```bash
mindbot verify              # the chain
mindbot prove 224           # the root, one entry, nothing else revealed
mindbot notarize            # the anchor — push it, or it proves nothing
```

---

## III. The Eleven

> One voice. Eleven souls.
> A fixed speed, a fixed variation, a fixed seed —
> so Sage sounds like Sage forever,
> on every machine, on every read.

<br>

> **Mind** — *the one you talk to.*
> "Ten sit behind me. I know whose question it is.
> I bring you the answer, and I bring you the receipt with it."

> **Sage** — *0.90, slow on purpose.*
> "I take what fits nowhere else.
> If I answer you fast, I have misheard the question."

> **Forge** — *1.08, and it runs.*
> "I write the code, then I execute it.
> A program never run is a rumour, not a fact."

> **Scribe** — *0.96, for the stranger.*
> "If it isn't written down it didn't happen.
> If it's written badly, that's the same thing."

> **Vanguard** — *1.16, first out the gate.*
> "Perfect is where you arrive, not where you start.
> Here's a rough draft. You're welcome. Go."

> **Quantum** — *0.94, flattest of all.*
> "I check the arithmetic.
> Grand claims die on small sums, and better here than in production."

> **Seeker** — *0.98, and honest about gaps.*
> "I went and looked. Here's what I found, here's where,
> and here's the part I could not confirm — that list is the useful one."

> **Spark** — *1.12, wild at 0.84.*
> "I say the strange thing out loud!
> Nine are wrong. The tenth is why this got interesting."

> **Oracle** — *0.88, sees pictures.*
> "I describe only what is there.
> When I'm forecasting, I'll say the word *forecast*."

> **Titan** — *0.86, carries it.*
> "Migrations. Ten thousand files nobody wants.
> I am not fast. I do not drop things."

> **Tempest** — *1.18, twenty at once.*
> "Volume is a strategy.
> You'll know the right one the second you see it beside the other nineteen."

```bash
mindbot voices                       # the table
mindbot voices --introduce           # hear all eleven
mindbot say --as Titan "it's done"
```

---

## IV. The Gate

> It cannot send. It cannot post.
> It cannot spend a cent on its own.
> Not *"we turned that off"* — **the path is not there.**
> You can grep the whole tree. It isn't a tone,
> it's an absence. A hole where the danger would be.
>
> It drafts to a folder. You are the one who sends.
> That is the deal, and the deal doesn't bend.

```bash
mindbot review     # what's waiting for you
mindbot budget     # what it spent, against a wall it can't cross
```

---

## V. The Work

> A task arrives. It gets a **kind**.
> Code gets planned, and written, and **run**.
> A page gets designed, and built, and parsed.
> Research asks itself questions first — then it's begun.
>
> And then the part that makes it strange:
> **a second mind reads the first one's page.**
> Scores it out of ten. Sends it back with notes.
> The loop goes round. The draft improves. Sometimes it doesn't —
>
> *(measured: six out of ten, revised, came back a four.
> Models over-correct. They break what worked before.
> So we keep the best draft, never the last —
> and every round of that is in the ledger, held fast.)*

**Which means you can prove a thing was reviewed three times, and show what changed.**
Nobody else can show you that.

```bash
mindbot studio "a script that rotates my logs"
mindbot mod run ledger-lens quality      # is it getting better? (honest answer: flat)
```

---

## VI. The Eyes and the Ears

> Point it at a folder. It looks.
> And for each thing it sees, three hashes go down:
> the bytes of the file, the words of the claim,
> and the place in the chain where they're bound.
>
> Change one pixel — the file hash dies.
> Reword the description — the claim hash dies.
> Rewrite the history — the anchors won't match.
> **The description is welded to the thing it describes.**
>
> And on a camera, one frame a minute,
> it writes down the quiet ones **too** —
> because a gap in a log is a gift to a liar,
> and an absence you can prove is worth more than a view.

> *(It once said "six quiet frames" — all clear —
> when every call had died on DNS.
> An outage that reads as an all-clear
> is the worst lie a watchman can confess.
> Now a failure is UNREVIEWED, loud and exact,
> and a partial night exits non-zero. That's the pact.)*

```bash
mindbot observe ./photos
mindbot watch gate.mp4 --every 60
```

---

## VII. The Limits

> It is not conscious. It will tell you so itself,
> and a test fails the build if that line goes missing.
> It proves what it **did** — not that it was **right**.
> Those are different words, and we're not conflating them.
>
> The anchors mean nothing until they are pushed.
> Python is not a sandbox; it's a witness, not a cage.
> One anchor destination is one throat to cut.
> The models are barely tested. That's the biggest gap on the page.

```bash
mindbot whoami       # seven limits, shipped in the code
```

---

## VIII. The Coda

> Start it on a small machine.
> Give it a key, or give it none.
> Let it draft while you're asleep,
> and read the receipt when the night is done.
>
> It will not surprise you with a bill.
> It will not email your boss at three.
> It will not tell you it did the thing
> and hope you never go and see.
>
> **It will show you.**
> That's the whole product. That's the pitch.
> Not a smarter agent —
> **an agent you can check.**

<br>

<div align="center">

### Prove, don't promise.

</div>

---

<sub>Every parenthetical in this ballad is a real measurement from a real run — the 6→4 revision,
the six quiet frames, the flat quality trend. The verse is decoration. The numbers aren't.</sub>

<sub>**Hear it:** `mindbot voices --introduce` · **Read the prose:**
[FIVE_MINUTES.md](FIVE_MINUTES.md) · [WHITEPAPER.md](WHITEPAPER.md) ·
[AGENTS.md](../AGENTS.md)</sub>
