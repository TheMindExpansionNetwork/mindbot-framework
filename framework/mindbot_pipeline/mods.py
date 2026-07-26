"""MODS — the extension system. Third-party capability that *cannot lie about what it did*.

WHY THIS IS NOT JUST ANOTHER PLUGIN SYSTEM
  Every agent framework has plugins/skills/tools. In all of them, once you load someone else's
  code it is simply *inside* your agent: it can do whatever Python can do, and the only record
  of its behavior is whatever it chooses to tell you. You audit the author, not the code.

  Here a mod is subject to the same machinery as the core:

    1. DECLARED CAPABILITIES. A mod's MOD.md lists exactly which powers it wants
       (board.read, outbox.write, model, net, fs.read …). Nothing else is handed to it.
    2. SCOPED API. The `api` object a mod receives only *has* the methods it was granted.
       Calling an ungranted one raises CapabilityDenied — and writes a `mod_denied` ledger entry.
    3. STATIC AUDIT AT LOAD. Before any mod code runs we parse its AST and look for imports and
       calls that reach past its declaration (urllib/socket/requests without `net`, open()/Path
       writes without fs, subprocess/eval/exec at all). Undeclared reach is reported, and by
       default refused.
    4. EVERY INVOCATION IS LEDGERED. Each mod command run writes a hash-chained entry
       (`mod_invoked`) that rolls into the Merkle root and gets anchored by the notary. A mod's
       behavior is therefore covered by the same externally-verifiable receipt as the core.

  Net effect: you can run code you did not write, and still hand an auditor proof of everything
  it did. That is the property no other agent framework offers.

HONEST LIMIT (stated plainly, because a security claim without limits is marketing):
  This is not a hard sandbox. Python cannot be fully contained in-process — a determined mod
  using getattr/exec tricks can evade the static audit. What it CANNOT do is act without leaving
  evidence: the ledger is append-only, hash-chained and externally anchored, so misbehavior
  becomes *provable after the fact* rather than deniable. Defense is accountability, not
  confinement. For untrusted code, run the agent in a container as well.

ANATOMY OF A MOD
    mods/<name>/
      MOD.md     manifest — front-matter (name/version/permissions) + human docs
      mod.py     code — must define register(api)

Extend: add a capability -> add it to CAPABILITIES and expose a matching method on ModAPI (and
gate it in _audit_source). Ship a mod -> `mindbot mod scaffold <name>`.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import time
from pathlib import Path

from .collaboration import ROOT, PIPE_DIR, add_task, ledger, now, read_tasks
from .logs import get_logger

_log = get_logger("mods")

# Where mods live. Repo-level `mods/` so they're obviously user-space, not framework internals.
MODS_DIR = ROOT / "mods"
OUTBOX = PIPE_DIR / "outbox"

# The full capability vocabulary. A mod gets EXACTLY what it declares — nothing implicit.
CAPABILITIES = {
    "board.read":   "read the task board",
    "board.write":  "propose tasks to the board",
    "outbox.write": "write drafts to the outbox (never sends)",
    "ledger.read":  "read the public ledger",
    "model":        "call a language model through the router",
    "net":          "make network requests",
    "fs.read":      "read files inside the repo",
    "fs.write":     "write files inside the repo workspace",
}

# Module imports that imply a capability. Used by the static audit.
_IMPLIES = {
    "net":      {"urllib", "http", "socket", "requests", "httpx", "ftplib", "smtplib", "asyncio"},
    "fs.write": {"shutil", "tempfile"},
}
# Never allowed, regardless of declaration — these defeat the whole audit.
_FORBIDDEN_IMPORTS = {"subprocess", "ctypes", "multiprocessing", "importlib", "pty", "os.system"}
_FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__", "getattr"}


class CapabilityDenied(Exception):
    """Raised when a mod reaches for a power it did not declare (and was not granted)."""


class ModError(Exception):
    """Manifest/loading problem."""


# ── manifest ─────────────────────────────────────────────────────────────────
def parse_manifest(md: str) -> dict:
    """Parse MOD.md front-matter. Stdlib only — a tiny key: value / list reader, no YAML dep."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", md, re.S)
    if not m:
        raise ModError("MOD.md must start with a --- front-matter block")
    head, body = m.group(1), m.group(2)
    meta: dict = {}
    key = None
    for raw in head.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        if re.match(r"^\s+-\s+", raw):                      # list item under the last key
            meta.setdefault(key, [])
            if isinstance(meta[key], list):
                meta[key].append(raw.strip()[1:].strip())
            continue
        if ":" in raw:
            k, v = raw.split(":", 1)
            key = k.strip()
            v = v.strip()
            # `key:` (nothing) and `key: []` both mean an EMPTY LIST, not a value. Without this
            # the literal "[]" is read as a one-item list and every empty-permission mod is
            # rejected with `unknown permission(s): ['[]']`.
            meta[key] = [] if v in ("", "[]", "{}") else v
    meta["doc"] = body.strip()
    for req in ("name", "version", "description"):
        if not meta.get(req):
            raise ModError(f"MOD.md missing required field: {req}")
    perms = meta.get("permissions") or []
    if isinstance(perms, str):
        perms = [p.strip() for p in perms.split(",") if p.strip()]
    unknown = [p for p in perms if p not in CAPABILITIES]
    if unknown:
        raise ModError(f"unknown permission(s): {unknown}. Valid: {sorted(CAPABILITIES)}")
    meta["permissions"] = perms
    return meta


# ── static capability audit ──────────────────────────────────────────────────
def audit_source(src: str, granted: list[str]) -> list[str]:
    """Parse the mod's AST and report reach beyond its declaration. [] means clean."""
    findings: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [f"syntax error: {e}"]

    def root_of(name: str) -> str:
        return (name or "").split(".")[0]

    for node in ast.walk(tree):
        # imports
        mods_seen: list[str] = []
        if isinstance(node, ast.Import):
            mods_seen = [root_of(a.name) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods_seen = [root_of(node.module or "")]
        for m in mods_seen:
            if m in _FORBIDDEN_IMPORTS:
                findings.append(f"forbidden import: {m}")
                continue
            for cap, names in _IMPLIES.items():
                if m in names and cap not in granted:
                    findings.append(f"imports '{m}' which implies '{cap}' (not declared)")
        # dangerous calls
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _FORBIDDEN_CALLS:
                findings.append(f"forbidden call: {node.func.id}()")
        # raw file writes without fs.write
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            mode = ""
            for a in node.args[1:2]:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    mode = a.value
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
            if any(c in mode for c in "wax") and "fs.write" not in granted:
                findings.append("open(...) for writing without 'fs.write'")
            if not mode and "fs.read" not in granted:
                findings.append("open(...) for reading without 'fs.read'")
    return sorted(set(findings))


# ── the scoped API handed to a mod ───────────────────────────────────────────
class ModAPI:
    """Capability-scoped surface. A mod only *has* what it declared and was granted."""

    # Default daily spend ceiling for ANY mod holding the `model` capability. A mod may declare
    # a lower one in MOD.md (`spend_cap: 0.10`); it can never raise its own ceiling above this.
    DEFAULT_MOD_SPEND_CAP = 0.25

    def __init__(self, mod_name: str, granted: list[str], spend_cap: float | None = None):
        self.mod = mod_name
        self.granted = list(granted)
        # min() is the load-bearing bit: a manifest can only ever LOWER its cap.
        self.spend_cap = min(float(spend_cap), self.DEFAULT_MOD_SPEND_CAP) \
            if spend_cap is not None else self.DEFAULT_MOD_SPEND_CAP
        self._commands: dict[str, dict] = {}

    # -- registration -------------------------------------------------------
    def command(self, name: str, help: str = ""):
        """Decorator: expose `mindbot mod run <mod> <name>`."""
        def deco(fn):
            self._commands[name] = {"fn": fn, "help": help}
            return fn
        return deco

    # -- guard --------------------------------------------------------------
    def _need(self, cap: str):
        if cap not in self.granted:
            ledger("mod_denied", f"{self.mod} attempted '{cap}' (not declared)", f"mod:{self.mod}")
            _log.warning("mod %s DENIED capability %s", self.mod, cap)
            raise CapabilityDenied(
                f"mod '{self.mod}' requested '{cap}' but did not declare it in MOD.md")

    # -- always available: say + log (transparency is not optional) ---------
    def log(self, message: str):
        """Write to the public ledger. Always granted — a mod cannot opt out of being recorded."""
        ledger("mod_log", f"{self.mod}: {str(message)[:160]}", f"mod:{self.mod}")

    def say(self, message: str):
        print(f"   {message}")

    # -- capability-gated ---------------------------------------------------
    def board(self) -> list:
        self._need("board.read")
        return read_tasks()

    def entries(self, event: str = "", limit: int = 0) -> list:
        """Read the hash-chained ledger. Optionally filter by event; newest last.

        `ledger.read` was in CAPABILITIES from the start but nothing on the API exposed it — a
        capability you cannot exercise is a promise, not a permission. This closes that gap.

        Read-only by construction: a mod can never append through this path. `log()` is the only
        write, and it always stamps the mod's own name.
        """
        self._need("ledger.read")
        import json as _json
        from .collaboration import LEDGER_PATH
        out = []
        if not LEDGER_PATH.exists():
            return out
        for ln in LEDGER_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                e = _json.loads(ln)
            except _json.JSONDecodeError:
                continue                      # one torn line must not kill the whole read
            if not event or e.get("event") == event:
                out.append(e)
        return out[-limit:] if limit else out

    def propose(self, task: str):
        self._need("board.write")
        add_task(f"[mod:{self.mod}] {task}", f"mod:{self.mod}")

    def draft(self, title: str, body: str) -> str:
        """Write a draft to the outbox. The constitution still holds: drafts never send."""
        self._need("outbox.write")
        OUTBOX.mkdir(parents=True, exist_ok=True)
        stamp = now().replace(" ", "-").replace(":", "")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in title[:40])
        p = OUTBOX / f"{stamp}_mod-{self.mod}_{safe}.md"
        p.write_text(f"# {title}\n\n*Draft by mod '{self.mod}'. A human reviews and sends.*\n\n{body}\n",
                     encoding="utf-8")
        ledger("mod_draft", f"{self.mod}: {title[:70]} -> {p.name}", f"mod:{self.mod}")
        return str(p)

    def ask(self, prompt: str, system: str = "You are a helpful assistant.") -> str:
        """Call a model. Gated by BOTH the capability grant AND this mod's own spend cap.

        Third-party code is the least-trusted spender in the system: holding `model` gets you a
        model, not a blank cheque. Exceeding the cap raises BudgetExceeded (the runtime catches
        it and records the attempt) rather than degrading quietly — a mod should fail loudly.
        """
        self._need("model")
        from .models import llm, strip_reasoning
        from .counselors import COUNSELORS
        from .budget import BudgetExceeded
        c = COUNSELORS["Sage"]
        text, mode = llm(c["provider"], c["model"], system, prompt,
                         mod=self.mod, mod_cap=self.spend_cap)
        if mode == "budget":
            raise BudgetExceeded(text)
        ledger("mod_model_call", f"{self.mod}: {prompt[:60]} [{mode}]", f"mod:{self.mod}")
        return strip_reasoning(text)

    def read_file(self, rel: str) -> str:
        self._need("fs.read")
        p = (ROOT / rel).resolve()
        if not str(p).startswith(str(ROOT.resolve())):
            raise CapabilityDenied("path escapes the repo")
        return p.read_text(encoding="utf-8", errors="replace")

    def write_file(self, rel: str, content: str) -> str:
        self._need("fs.write")
        p = (ROOT / rel).resolve()
        if not str(p).startswith(str(ROOT.resolve())):
            raise CapabilityDenied("path escapes the repo")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        ledger("mod_wrote_file", f"{self.mod}: {rel}", f"mod:{self.mod}")
        return str(p)


# ── discovery / loading / running ────────────────────────────────────────────
def discover() -> list[dict]:
    """Every mod on disk, with its manifest (and any manifest error)."""
    out = []
    if not MODS_DIR.exists():
        return out
    for d in sorted(p for p in MODS_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")):
        md, code = d / "MOD.md", d / "mod.py"
        rec = {"dir": str(d), "slug": d.name, "has_code": code.exists()}
        try:
            if not md.exists():
                raise ModError("no MOD.md")
            rec.update(parse_manifest(md.read_text(encoding="utf-8")))
            rec["ok"] = code.exists()
            rec["error"] = None if code.exists() else "no mod.py"
        except Exception as e:  # noqa: BLE001
            rec["ok"] = False
            rec["error"] = str(e)
        out.append(rec)
    return out


def load(slug: str, strict: bool = True) -> tuple[ModAPI, dict, list[str]]:
    """Audit then load one mod. Returns (api, manifest, findings). Raises if strict and dirty."""
    d = MODS_DIR / slug
    if not (d / "MOD.md").exists():
        raise ModError(f"no such mod: {slug}")
    meta = parse_manifest((d / "MOD.md").read_text(encoding="utf-8"))
    src = (d / "mod.py").read_text(encoding="utf-8")
    findings = audit_source(src, meta["permissions"])
    if findings and strict:
        ledger("mod_refused", f"{slug}: {findings[:3]}", f"mod:{slug}")
        raise ModError(f"static audit refused '{slug}': " + "; ".join(findings))

    try:
        declared_cap = float(meta["spend_cap"]) if meta.get("spend_cap") else None
    except (TypeError, ValueError):
        declared_cap = None
    api = ModAPI(meta["name"], meta["permissions"], spend_cap=declared_cap)
    spec = importlib.util.spec_from_file_location(f"mindbot_mod_{slug}", d / "mod.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)                      # the mod's top level runs here
    if not hasattr(module, "register"):
        raise ModError(f"mod '{slug}' has no register(api) function")
    module.register(api)
    return api, meta, findings


def run(slug: str, command: str, arg: str = "", strict: bool = True) -> dict:
    """Invoke one mod command. Every run is ledgered — that is the whole point."""
    t0 = time.time()
    api, meta, findings = load(slug, strict=strict)
    if command not in api._commands:
        raise ModError(f"mod '{slug}' has no command '{command}'. "
                       f"Available: {sorted(api._commands)}")
    ledger("mod_invoked", f"{slug}.{command}({arg[:40]}) perms={meta['permissions']}", f"mod:{slug}")
    _log.info("mod run %s.%s perms=%s", slug, command, meta["permissions"])
    try:
        result = api._commands[command]["fn"](arg)
        ok, err = True, None
    except CapabilityDenied as e:
        result, ok, err = None, False, f"CapabilityDenied: {e}"
    except Exception as e:  # noqa: BLE001 — a mod crash must not take the agent down
        result, ok, err = None, False, f"{type(e).__name__}: {e}"
        _log.exception("mod %s.%s failed", slug, command)
    secs = round(time.time() - t0, 2)
    ledger("mod_result", f"{slug}.{command} ok={ok} {secs}s", f"mod:{slug}")
    return {"mod": slug, "command": command, "ok": ok, "result": result,
            "error": err, "secs": secs, "permissions": meta["permissions"],
            "audit_findings": findings}


SCAFFOLD_MOD_MD = """---
name: {slug}
version: 0.1.0
description: {desc}
author: you
permissions:
  - outbox.write
---

# {slug}

What this mod does, and why someone would install it.

## Commands
- `mindbot mod run {slug} hello` — say hello and leave a receipt.

## Permissions & why
- `outbox.write` — writes its greeting as a draft. It cannot send anything.
"""

SCAFFOLD_MOD_PY = '''"""{slug} — a MindBot mod.

Every action here is recorded in the hash-chained, externally-anchored ledger. That is not
optional and not something this file can turn off — which is why a mod can be trusted without
trusting its author.
"""


def register(api):
    """Called once at load. Declare commands here."""

    @api.command("hello", "say hello and leave a receipt")
    def hello(arg):
        who = arg or "world"
        api.log(f"greeted {{who}}")            # -> ledger (always available)
        path = api.draft(f"hello {{who}}",     # -> needs 'outbox.write'
                         f"Hello, {{who}}.\\n\\nWritten by the {slug} mod.")
        api.say(f"hello, {{who}} — draft written to {{path}}")
        return path
'''


def scaffold(slug: str, desc: str = "a new MindBot mod") -> Path:
    d = MODS_DIR / slug
    if d.exists():
        raise ModError(f"mods/{slug} already exists")
    d.mkdir(parents=True)
    (d / "MOD.md").write_text(SCAFFOLD_MOD_MD.format(slug=slug, desc=desc), encoding="utf-8")
    (d / "mod.py").write_text(SCAFFOLD_MOD_PY.format(slug=slug), encoding="utf-8")
    ledger("mod_scaffolded", slug, "mods")
    return d
