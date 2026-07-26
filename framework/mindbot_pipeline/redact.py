"""REDACT — keep secrets OUT of an immutable record. Prevention, because there is no cure.

THE PROBLEM THIS SOLVES (a genuine design flaw in append-only ledgers)
  Our ledger is append-only and hash-chained, and its Merkle roots are published to a third
  party. Those are features — until a secret gets written into it. Then:

    * you cannot delete the entry: every later `prev` hash depends on it;
    * you cannot edit it: `verify()` would report tampering, correctly;
    * you cannot rewrite history: the notary's published anchors would stop matching;
    * and if you already pushed, the secret is in a public repo AND in a Merkle root.

  Every property that makes the ledger trustworthy also makes a leaked secret PERMANENT. The
  only place this can be fixed is BEFORE the write. So this module is called on the ledger's
  write path, unconditionally, for every entry.

  This is the same reason `verify` is honest: we would rather refuse to record a secret than
  own a beautiful, tamper-evident, permanently-leaked API key.

WHAT IT CATCHES
  Provider API keys (OpenRouter/OpenAI/Anthropic/xAI/Google/Stripe/AWS/GitHub/Slack/HF), bearer
  tokens, private-key PEM blocks, JWTs, connection strings with inline passwords, and
  `KEY=value` pairs whose NAME looks secret (api_key, token, secret, password, …).

WHAT IT DELIBERATELY DOES NOT DO
  It does not try to detect "any high-entropy string" — that flags git SHAs, Merkle roots and
  model hashes, which are exactly what this ledger is full of. False positives on our own hashes
  would make the ledger unreadable. Known-shape secrets only.

Extend: add a provider -> append a (name, compiled pattern) to PATTERNS. Keep patterns
ANCHORED and specific; a greedy pattern here silently corrupts the audit trail.
"""
from __future__ import annotations

import re

# Each entry: (label, pattern). Order matters only for readability — all are applied.
# Patterns are intentionally shape-specific (prefix + length) rather than entropy-based.
PATTERNS: list[tuple[str, re.Pattern]] = [
    # ORDER IS LOAD-BEARING for the `sk-` family: the generic OpenAI shape would otherwise
    # swallow `sk-or-` and `sk-ant-` keys and mislabel them. The label is what tells an operator
    # WHICH provider to rotate, so a wrong label is nearly as bad as no redaction. Specific
    # prefixes first, and the generic pattern additionally excludes them via lookahead.
    ("openrouter",  re.compile(r"sk-or-v1-[A-Za-z0-9]{16,}")),
    ("anthropic",   re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai",      re.compile(r"sk-(?!or-|ant-)(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("xai",         re.compile(r"xai-[A-Za-z0-9]{20,}")),
    ("google",      re.compile(r"AIza[A-Za-z0-9_-]{30,}")),
    ("stripe",      re.compile(r"[rs]k_(?:live|test)_[A-Za-z0-9]{16,}")),
    ("github",      re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("aws",         re.compile(r"AKIA[0-9A-Z]{16}")),
    ("slack",       re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("huggingface", re.compile(r"hf_[A-Za-z0-9]{30,}")),
    ("jwt",         re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("pem",         re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
    ("bearer",      re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}")),
    # postgres://user:password@host  — the password, not the whole URL
    ("conn-string", re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://[^\s:@/]+):([^\s@/]{4,})@")),
    # NAME=value / "NAME": "value" where the NAME looks secret.
    # NOTE: this one is heavily guarded below (see _is_real_secret_value / _NOT_SECRET_NAMES).
    # Naively, it fires on `max_tokens=200`, `tokenizer=tok`, and `secrets=[Secret.from_name(..)]`
    # — a scanner with 100% false positives gets muted, which is worse than having none.
    ("named-secret", re.compile(
        r"(?i)\b([a-z0-9_.\-]*(?:api[_-]?key|secret|passwd|password|token|auth|credential)"
        r"[a-z0-9_.\-]*)\s*[:=]\s*[\"']?([^\s\"',;]{8,})")),
]

# Names that merely CONTAIN a secret-ish word but never hold a credential.
_NOT_SECRET_NAMES = re.compile(
    r"(?i)^(?:max_?tokens?|min_?tokens?|n_?tokens?|num_?tokens?|tokens?_?(?:count|used|in|out|per\w*)"
    r"|tokenizer\w*|_?token(?:_?re|_?pat\w*)?|secrets?|auth_?(?:method|type|url|header|flow)"
    r"|token_?type|credential_?type|password_?(?:field|input|label|prompt))$")

# Values that are obviously not real credentials.
_PLACEHOLDER = re.compile(
    # Ellipsis is matched ANYWHERE (not anchored): docs write `sk_live_...` inside backticks, so
    # an end-anchor never fires. Both ASCII "..." and the unicode "…" appear in our own docs.
    # xxxx has NO leading \b either — `sk_live_xxxxxxxx` has a word char before the x-run.
    r"(?i)\.{3}|…|<[^>]*>|x{4,}|your[_-]?\w*|example|changeme|placeholder|\byour\b")

# Path-like values (`docs/AUTH.md`, ./config.json) are references, never credentials.
_PATHLIKE = re.compile(r"^[./~]|[/\\].*\.[a-z0-9]{1,5}$", re.I)


def _is_real_secret_value(name: str, value: str) -> bool:
    """Guard for `named-secret`: does this VALUE plausibly hold a credential?

    Rejects: known non-secret names, numbers (max_tokens=200), code expressions
    (secrets=[Secret.from_name(..)], tokenizer=tok), and placeholders (sk-or-v1-…, <your-key>).
    """
    # strip quoting AND markdown backticks — docs write `KEY=sk_live_...` and the trailing
    # backtick otherwise defeats every end-anchored placeholder check.
    # Two views of the value, deliberately:
    #   v      — quotes/backticks stripped. Used for the PLACEHOLDER test, which must still see
    #            trailing dots ("sk_live_..."); stripping them would turn every doc example
    #            into a reported live key.
    #   v_trim — additionally trimmed of sentence punctuation. Used for the PATH test, because
    #            prose writes "Auth: `docs/AUTH.md`." and the period breaks the end-anchor.
    n = name.strip().strip("\"'`")
    v = value.strip().strip("\"'`")
    v_trim = v.rstrip(".,;:!?)`\"'")
    if _PATHLIKE.search(v_trim):
        return False
    if _NOT_SECRET_NAMES.match(n):
        return False
    if not v or len(v) < 8:
        return False
    if v.replace(".", "").replace("_", "").isdigit():        # max_tokens=200
        return False
    if v[0] in "[({" or "(" in v or v.startswith(("re.", "os.", "self.", "modal.")):
        return False                                          # a code expression, not a value
    if _PLACEHOLDER.search(v):                                # sk-or-v1-… / <your-key> / xxxx
        return False
    if v.isidentifier() and "_" not in v and len(v) < 16:     # tokenizer=tok
        return False
    return True

MASK = "[REDACTED:{label}]"


def scrub(text: str) -> tuple[str, list[str]]:
    """Return (clean_text, labels_found). Safe on any input; never raises."""
    if not text:
        return text, []
    found: list[str] = []
    out = str(text)
    for label, pat in PATTERNS:
        if label == "conn-string":
            # keep the scheme+user so the entry stays useful; mask only the password
            def _c(m):
                found.append(label)
                return f"{m.group(1)}:{MASK.format(label=label)}@"
            out = pat.sub(_c, out)
        elif label == "named-secret":
            # keep the KEY NAME (that is the useful signal) and mask only the VALUE — but only
            # when the value actually looks like a credential (see _is_real_secret_value).
            def _n(m):
                if not _is_real_secret_value(m.group(1), m.group(2)):
                    return m.group(0)                 # leave the text untouched
                found.append(label)
                return f"{m.group(1)}={MASK.format(label=label)}"
            out = pat.sub(_n, out)
        else:
            if pat.search(out):
                found.append(label)
                out = pat.sub(MASK.format(label=label), out)
    return out, sorted(set(found))


def is_clean(text: str) -> bool:
    return not scrub(text)[1]


def scan(text: str) -> list[str]:
    """Labels of any secrets present. For pre-commit / pre-push checks."""
    return scrub(text)[1]


# Allowlist pragmas — the same escape hatch gitleaks/detect-secrets provide, and necessary for
# the same reason: test fixtures and documentation legitimately contain key-SHAPED strings.
# Without this the scanner flags its own test data, and a scanner you have to ignore is dead.
#   file-level : put `mindbot:allow-secrets` in the first 10 lines -> whole file skipped
#   line-level : append `# mindbot:allow-secret`                   -> that line skipped
ALLOW_FILE = "mindbot:allow-secrets"
ALLOW_LINE = "mindbot:allow-secret"


def scan_paths(paths) -> list[dict]:
    """Scan files for secrets. Returns [{path, line, labels, preview}] — used by `mindbot scan`.

    Skips its OWN pattern definitions (or it reports itself every run) and honours the
    allowlist pragmas above.
    """
    import pathlib
    hits: list[dict] = []
    for p in paths:
        p = pathlib.Path(p)
        if not p.is_file() or p.name == "redact.py":
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lines = text.splitlines()
        if any(ALLOW_FILE in ln for ln in lines[:10]):     # file-level opt-out
            continue
        for i, line in enumerate(lines, 1):
            if ALLOW_LINE in line:                          # line-level opt-out
                continue
            labels = scan(line)
            if labels:
                masked, _ = scrub(line.strip())
                hits.append({"path": str(p), "line": i, "labels": labels,
                             "preview": masked[:110]})
    return hits
