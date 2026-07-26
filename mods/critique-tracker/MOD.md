---
name: critique-tracker
version: 0.1.0
description: Tracks critique scores by counselor to identify most reliable reviewers
author: forged by MindBot
permissions:
  - fs.read
  - fs.write
  - ledger.read
---

# critique-tracker

Tracks critique scores by counselor to identify most reliable reviewers

## Commands

| Command | What it does |
|---|---|
| `mindbot mod run critique-tracker critique record` | Record a critique score: critique record <counselor> <score 1-10> [task-id] [notes] |
| `mindbot mod run critique-tracker critique stats` | Show counselor rankings by average score: critique stats [--top N] |
| `mindbot mod run critique-tracker critique history` | Show all critiques for a counselor: critique history <counselor> |
| `mindbot mod run critique-tracker critique import` | Scan ledger for historical critiques and populate local DB: critique import |

## Permissions & why

fs.read/fs.write maintain local critique database (counselor->scores[]). ledger.read imports historical critique entries on first run. No board/net/model needed — critiques recorded via CLI commands.

Every capability here is checked twice — statically against this file before the mod loads, and
again at each call. Anything undeclared raises `CapabilityDenied`, the call does not happen, and
the attempt is written to the hash-chained ledger.

---
*Forged 2026-07-25 08:34 · `mindbot mod info critique-tracker` for the audit result.*
