---
# ─── copy this file to mods/<your-slug>/MOD.md and edit ───────────────────────
# Everything above the second `---` is the MANIFEST. It is parsed, not decorative.
name: my-mod                    # kebab-case, must match the folder name
version: 0.1.0
description: One line. Shown in `mindbot mod list` — write it for a stranger.
author: your name or handle
permissions:                    # DECLARE THE FEWEST THAT WORK. See the table below.
  - outbox.write
---

# my-mod

<!--
  WHY THE MANIFEST MATTERS MORE THAN IT LOOKS
  ───────────────────────────────────────────
  This is not documentation that happens to sit next to code. Before your mod loads, MindBot
  walks your `mod.py` as an AST and checks it against the `permissions` list above.

    * Reach for something you did NOT declare  -> CapabilityDenied. The call does not happen,
      and the ATTEMPT is written to the hash-chained ledger.
    * Declare something you never use          -> it still loads, but you have handed yourself
      a power you did not need, and anyone auditing your mod can see that.

  So the manifest is a promise the runtime enforces on your behalf. That is what makes it
  possible to run a mod you did not write and still know what it did.

  Delete these comments when you publish.
-->

One paragraph: what does this mod do, and who is it for? Lead with the verb.

## Commands

| Command | What it does |
|---|---|
| `mindbot mod run my-mod hello [arg]` | say hello and leave a draft in the outbox |

## Permissions & why

Justify each one. A reviewer should be able to read this table and predict exactly what your
code can touch.

| Capability | Why this mod needs it |
|---|---|
| `outbox.write` | writes its result as a draft — it can never send anything |

**Deliberately not requested:** `model`, `net`, `fs.write`, `board.write`.
<!-- Saying what you did NOT ask for is worth more than saying what you did. It tells a
     reviewer you thought about it, and the static audit will hold you to it. -->

## Try it

```bash
mindbot mod info my-mod          # manifest + static audit result
mindbot mod run my-mod hello you
mindbot verify                   # the chain covering everything it just did
```

---

## THE CAPABILITY TABLE

| Capability | Grants | Cost / risk |
|---|---|---|
| `outbox.write` | `api.draft(title, body)` — write a draft | none; drafts never send |
| `board.read` | `api.board()` — read the task list | none |
| `board.write` | `api.propose(task)` — add tasks | can fill the queue |
| `ledger.read` | `api.entries(event, limit)` — read the chain | none; read-only |
| `model` | `api.ask(prompt)` — call a language model | **spends money** (capped) |
| `net` | outbound HTTP | **data leaves the machine** |
| `fs.read` | `api.read_file(rel)` inside the repo | none |
| `fs.write` | `api.write_file(rel, content)` inside the repo | can overwrite work |

`api.log()` and `api.say()` are **always** available and cannot be switched off. A mod does not
get to opt out of being recorded.

### Spend

A mod that declares `model` gets a spend cap (default **$0.25**). It may LOWER its own cap and
can never raise it — the runtime takes `min(requested, default)`. If you need more, the operator
raises it, not you.

---

## THE CODE (`mod.py`)

```python
"""my-mod — one line about what this does."""


def register(api):
    """Called once at load. Declare commands with @api.command."""

    @api.command("hello", "say hello and leave a draft")
    def hello(arg):
        who = (arg or "world").strip()
        api.log(f"greeted {who}")               # always available; always recorded
        api.say(f"hello, {who}")                # prints to the operator
        return api.draft("hello", f"Hello, {who}.\n")   # needs outbox.write
```

Every command takes exactly one `arg` string. Return whatever is useful — it is shown and
recorded.

### The rules that will bite you

1. **Standard library only**, unless you are certain of the target machine. The core ships
   stdlib-only so there is no dependency tree to audit; a mod that breaks that inherits the
   problem.
2. **Never call a provider directly.** Use `api.ask()`. Bypassing it also bypasses
   `budget.check()`, which is the only thing between an unattended loop and an empty account.
3. **Do not add a send path.** No SMTP, no webhooks, no payments. It is the one rule with no
   exception, and a mod that adds one will not be merged.
4. **Fail loudly.** A mod that swallows its own error and returns "ok" is worse than one that
   crashes — silent failure is the exact thing this framework exists to make impossible.

---

## Scaffold it instead of copying

```bash
mindbot mod scaffold my-mod      # writes both files, wired and audited
mindbot forge mod "tracks which counselor writes best"   # generates a COMPLETE mod
```

`mindbot forge mod` designs the capability list from a description, writes the code, and runs
the real static auditor **before** anything touches disk — because generating a mod the loader
would then refuse just looks like a broken loader.

## Publishing

1. `mindbot mod info my-mod` — the audit must be clean.
2. `mindbot scan` — no secrets. The ledger is append-only and publicly anchored; a key that
   lands in it cannot be deleted, edited, or rewritten.
3. Open a PR with your `mods/my-slug/` folder. The manifest is the review.

<sub>Full reference: [`docs/MODS.md`](../docs/MODS.md) · contract for AI authors:
[`AGENTS.md`](../AGENTS.md)</sub>
