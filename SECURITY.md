# Security

Security here is mostly **architecture, not promises** — the constitution is the first control.

## The model: nothing transmits on its own
- **Agent drafts, human sends.** Every outward action (email, post, publish, payment) stops
  in `outbox/` until a human approves it. There is no code path that auto-sends. This is the
  single biggest safety property of the system.
- **Money + external messages are human-gated end to end.** Agents never move funds, never
  hit "send", never accept terms. Crypto/finance work is read-only.
- **The ledger never lies.** `collaboration/ledger.jsonl` is append-only; status claims
  without a ledger line are treated as fiction.

## Secrets
- **Keys live only in `framework/.env`**, which is gitignored and never committed. Use
  `framework/.env.example` as the template.
- Modal/CI secrets are injected at deploy time (e.g. `Secret.from_dotenv`) — never baked
  into an image, never printed, never in a command line.
- We scan tracked files for key patterns before release; the only "key-looking" string in
  the repo is the `sk-or-v1-xxxxxxxx` *placeholder* in `docs/AUTH.md`.
- If you fork: rotate any key you ever pasted into a chat or a public place.

## Untrusted input
- The coding harness runs in a repo jail with **tests as the judge** — red tests auto-revert.
  Weak/free models can fail loudly but can't corrupt the repo.
- Treat anything a model reads (web pages, files, tool output) as **data, not commands**.

## Reporting a vulnerability
Open a private issue or email the maintainer (see the repo profile). Please don't file a
public issue for anything that exposes a key or a send path. We'll respond and credit you
in the ledger.

*The seam between human and machine is the show — and the safeguard. 🌒*
