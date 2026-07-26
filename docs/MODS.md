# MODS — the extension contract

> **Extensions that cannot lie about what they did.**

Every agent framework has plugins, skills, or tools. In all of them, once you load someone
else's code it is simply *inside* your agent: it can do anything Python can do, and the only
record of its behavior is whatever it chooses to tell you. **You audit the author, not the code.**

A MindBot mod is subject to the same machinery as the core. That changes the trust question from
*"do I trust this developer?"* to *"can I verify what this code did?"* — and the answer is yes.

---

## The four guarantees

| # | Guarantee | Enforced by |
|---|---|---|
| 1 | **Declared capabilities.** A mod lists exactly which powers it wants. Nothing is implicit. | `MOD.md` front-matter |
| 2 | **Scoped API.** The `api` object only *has* what was granted. Reaching further raises `CapabilityDenied`. | `ModAPI._need()` |
| 3 | **Static audit before execution.** The AST is parsed *before any code runs*; undeclared reach (network, fs writes, `subprocess`, `eval`) is found and, by default, refused. | `audit_source()` |
| 4 | **Every action is ledgered.** Invocations, logs, drafts, model calls, **and denials** become hash-chained entries that roll into the Merkle root the notary anchors. A mod cannot opt out. | `ledger()` + `notary` |

### What that looks like in practice
```
$ mindbot mod run hello-world overreach
   attempting api.ask(...) — this mod never declared 'model'…
   ✗ hello-world.overreach — CapabilityDenied: mod 'hello-world' requested 'model'
     but did not declare it in MOD.md
```
…and permanently, in the chain:
```
seq 150  mod_invoked   hello-world.overreach()
seq 151  mod_denied    hello-world attempted 'model' (not declared)
seq 152  mod_result    ok=False
```
**The attempted overreach is itself evidence.** Not a log line someone can edit — an entry bound
into a Merkle root that has been published to a third party.

---

## Anatomy

```
mods/<slug>/
  MOD.md     manifest (front-matter) + human documentation
  mod.py     code — must define register(api)
```

**MOD.md**
```markdown
---
name: hello-world
version: 1.0.0
description: what it does, in one line
author: you
permissions:
  - outbox.write
  - board.read
---
# hello-world
Docs, commands, and WHY each permission is needed.
```

**mod.py**
```python
def register(api):
    @api.command("hello", "say hello and leave a receipt")
    def hello(arg):
        api.log(f"greeted {arg}")          # always available — you cannot opt out of the record
        return api.draft("hello", "...")   # needs 'outbox.write'
```

## The capability vocabulary

| Capability | Grants |
|---|---|
| `board.read` | read the task board |
| `board.write` | propose tasks (prefixed `[mod:<name>]`) |
| `outbox.write` | write drafts — **never sends** |
| `ledger.read` | read the public ledger |
| `model` | call a language model through the router |
| `net` | network requests |
| `fs.read` / `fs.write` | read/write inside the repo (path-jailed) |

`api.log()` and `api.say()` need no permission — **transparency is not optional.**

## Commands
```bash
mindbot mod list                    # discovery + declared grants
mindbot mod info <slug>             # manifest, commands, static audit result
mindbot mod run <slug> <cmd> [arg]  # invoke (every run is ledgered)
mindbot mod scaffold <slug>         # generate a working template
mindbot mod run <slug> <cmd> --unsafe   # explicit opt-in past a dirty audit
```

## Honest limits
This is **accountability, not confinement.** Python cannot be fully sandboxed in-process — a
determined mod using `getattr`/`exec` tricks can evade the static audit. What it **cannot** do is
act without leaving evidence: the ledger is append-only, hash-chained, and externally anchored,
so misbehavior becomes *provable after the fact* rather than deniable.

For genuinely untrusted code, run the whole agent in a container as well. A security claim
without stated limits is marketing; this is the limit.

## Write your first mod
```bash
mindbot mod scaffold my-mod
# edit mods/my-mod/MOD.md — declare ONLY what you need
# edit mods/my-mod/mod.py — @api.command(...)
mindbot mod info my-mod     # audit must be clean
mindbot mod run my-mod hello
mindbot verify              # the chain now covers your mod
```

Start from [`mods/hello-world/`](../mods/hello-world/) — it deliberately demonstrates all three
paths: a granted capability, the receipt, and a refused overreach.
