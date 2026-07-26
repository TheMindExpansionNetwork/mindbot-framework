---
name: hello-world
version: 1.0.0
description: The reference mod — proves the capability system, the receipt, and the denial path.
author: The Mind Expansion Network
permissions:
  - outbox.write
  - board.read
---

# hello-world

The template. Copy this folder, rename it, and you have a mod. It exists to *demonstrate the
three guarantees* rather than to do anything useful:

1. **Granted capability works.** It declared `outbox.write`, so `api.draft(...)` succeeds.
2. **Every action leaves a receipt.** `api.log(...)` and every capability call write
   hash-chained ledger entries that roll into the Merkle root and get anchored by the notary.
   The mod cannot turn this off.
3. **Ungranted capability is refused.** The `overreach` command deliberately reaches for
   `model` — which this mod did **not** declare — and gets `CapabilityDenied`, plus a
   `mod_denied` entry in the ledger. *An attempted overreach is itself recorded.*

## Commands
| Command | What it shows |
|---|---|
| `mindbot mod run hello-world hello [name]` | a granted capability + a receipt |
| `mindbot mod run hello-world peek` | reads the board (`board.read`) |
| `mindbot mod run hello-world overreach` | **denial in action** — reaches for an undeclared power |

## Permissions & why
- `outbox.write` — writes its greeting as a draft. It **cannot send** anything, ever.
- `board.read` — counts open tasks so `peek` has something honest to report.

Deliberately **not** requested: `model`, `net`, `fs.write`. The static audit at load time would
refuse this mod if its code reached for any of them.

## Try it
```bash
mindbot mod list                       # discovery + declared permissions
mindbot mod info hello-world           # manifest + static audit result
mindbot mod run hello-world hello you  # works
mindbot mod run hello-world overreach  # DENIED, and the attempt is on the record
mindbot verify                         # the chain covering all of the above
```

## Make your own
```bash
mindbot mod scaffold my-mod
```
Then edit `mods/my-mod/MOD.md` (declare only what you need) and `mods/my-mod/mod.py`.
