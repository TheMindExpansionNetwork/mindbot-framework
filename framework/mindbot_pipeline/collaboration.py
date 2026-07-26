"""Read/write the 12_Agent_Collaboration files — the swarm's shared memory.

Every counselor session starts by reading these and ends by writing them.
Plain markdown + JSON so any model, any year, can parse them until 2045.

Extend: add a shared-file mutator -> define it, then append its name to the
_locked() wrap-list at the bottom so it's swarm-safe; gate a new human-only task
class -> add a marker substring to HUMAN_GATED; surface a new metric on the
dashboard -> add a key in update_dashboard().
"""

import datetime
import functools
import hashlib
import json
import os
import re
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIPE_DIR = Path(__file__).resolve().parents[1]

# Swarm-safety: many councilors can pulse CONCURRENTLY (see nucleus.swarm). All shared-file
# read-modify-write goes through this one re-entrant lock so two workers can't double-claim a
# task or corrupt state.json/dashboard_state.json. The slow model work happens OUTSIDE the lock.
_LOCK = threading.RLock()


class _CrossProcessLock:
    """An OS-level exclusive file lock — the ONLY thing that makes the hash chain sound.

    A threading lock is scoped to ONE process. The real deployment runs `mindbot pulse` from
    cron *while* a human runs commands, i.e. multiple PROCESSES appending to the same ledger.
    Measured before this existed: 3 concurrent writers produced 17 duplicate seq numbers, lost
    3 entries, and broke the chain at seq 2 — which would make `mindbot verify` report BROKEN
    and collapse the entire proof story in normal use.

    stdlib only: msvcrt on Windows, fcntl elsewhere. Fails OPEN (a lock we cannot take must not
    deadlock the agent) — degraded to the old behavior rather than hanging forever.
    """

    def __init__(self, path: Path, timeout: float = 10.0):
        self.path = Path(str(path) + ".lock")
        self.timeout = timeout
        self._fh = None

    def __enter__(self):
        import time
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + self.timeout
        while True:
            try:
                self._fh = open(self.path, "a+b")
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if self._fh:
                    self._fh.close()
                    self._fh = None
                if time.time() >= deadline:
                    return self          # fail OPEN — never hang the agent on a stuck lock
                time.sleep(0.02)

    def __exit__(self, *exc):
        if self._fh:
            try:
                if os.name == "nt":
                    import msvcrt
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            self._fh.close()
            self._fh = None
        return False


def _locked(fn):
    """Serialize a shared-file mutator across swarm worker threads."""
    @functools.wraps(fn)
    def _wrapped(*a, **k):
        with _LOCK:
            return fn(*a, **k)
    return _wrapped


# Layout autodetection: the framework runs identically in the original idea
# workspace (numbered folders) and the clean MINDBOTZ repo (named folders).
def _pick(*candidates: str) -> Path:
    for c in candidates:
        if (ROOT / c).exists():
            return ROOT / c
    p = ROOT / candidates[-1]
    p.mkdir(parents=True, exist_ok=True)
    return p


COLLAB = _pick("12_Agent_Collaboration", "collaboration")
DASH_DIR = _pick("13_Project_Visuals_and_Dashboard", "dashboard")
DATASET_OUT = _pick("15_Synthetic_Dataset/output", "dataset/output")
TODO_PATH = COLLAB / "BIG_TODO_LIST.md"
HANDOFF_PATH = COLLAB / "AGENT_HANDOFF_NOTES.md"
LEDGER_PATH = COLLAB / "ledger.jsonl"
STATE_PATH = PIPE_DIR / "state.json"
DASH_STATE = DASH_DIR / "dashboard_state.json"

# Groups: 1=mark (' '=open, 'x'=done, '~'=in-progress), 2=optional claim tag, 3=task text.
# read_tasks / claim_task / complete_task all depend on this shape — change in lockstep.
TASK_RE = re.compile(r"^- \[( |x|~)\] (?:\((claimed: [^)]+)\) )?(.+)$")


def now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def load_state() -> dict:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ── tamper-evident ledger: each entry binds the SHA-256 of the one before it ──
# This makes the agent's ENTIRE autonomous history verifiable (see provenance.py): any
# edit / insert / delete breaks the chain and is detectable. Backward compatible — older
# pre-chain entries simply lack the seq/prev/hash fields and are skipped by the verifier.
#
# The chain HEAD (last seq + hash) is kept in a tiny sidecar file next to the ledger, keyed
# to the ledger path. Reading it fresh on every write makes the chain correct across process
# restarts AND when the path is swapped (e.g. tests) — no fragile shared in-memory state.
_GENESIS = "0" * 64


def _head_path():
    return LEDGER_PATH.with_name(LEDGER_PATH.name + ".head")


def _ledger_hash(entry: dict, prev: str) -> str:
    blob = f"{entry['seq']}|{entry['ts']}|{entry['agent']}|{entry['event']}|{entry['detail']}|{prev}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _scan_head() -> tuple:
    """Derive (seq, hash) of the last hash-bearing entry by scanning the ledger file."""
    last = None
    if LEDGER_PATH.exists():
        for ln in LEDGER_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                e = json.loads(ln)
                if "hash" in e and "seq" in e:
                    last = e
            except Exception:  # noqa: BLE001
                continue
    return (last["seq"], last["hash"]) if last else (0, _GENESIS)


def _read_head() -> tuple:
    """Current chain head — from the sidecar (fast) or derived from the file (fallback)."""
    hp = _head_path()
    if hp.exists():
        try:
            h = json.loads(hp.read_text(encoding="utf-8"))
            return int(h["seq"]), h["hash"]
        except Exception:  # noqa: BLE001 — bad sidecar: rederive from the file of record
            pass
    return _scan_head()


def ledger(event: str, detail: str, agent: str = "framework") -> None:
    """The ledger never lies — and now it can PROVE it. Append-only + hash-chained.

    The whole read-head -> append -> write-head sequence MUST be atomic across processes. If two
    writers interleave, both read the same head, both claim seq N+1, and the chain forks — which
    is exactly what a verifier reports as tampering. The cross-process lock (not just the
    threading one) is what makes the integrity guarantee real outside a single process.
    """
    # SCRUB BEFORE WRITE. The chain is append-only and its roots are published, so a secret
    # written here is PERMANENT — unremovable without breaking every later hash and every
    # anchor. There is no cure, only prevention, and this is the only place to apply it.
    from .redact import scrub
    detail, leaked = scrub(str(detail))
    if leaked:
        detail = f"{detail}  [ledger scrubbed: {','.join(leaked)}]"

    with _CrossProcessLock(LEDGER_PATH):
        seq_prev, prev = _read_head()
        seq = seq_prev + 1
        entry = {"seq": seq, "ts": now(), "agent": agent, "event": event,
                 "detail": detail, "prev": prev}
        entry["hash"] = _ledger_hash(entry, prev)
        with LEDGER_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())      # durable before the head advances, or a crash forks it
        try:
            _head_path().write_text(json.dumps({"seq": seq, "hash": entry["hash"]}),
                                    encoding="utf-8")
        except Exception:  # noqa: BLE001 — sidecar is a cache; the file of record already has it
            pass


def read_tasks() -> list[dict]:
    """Parse BIG_TODO_LIST.md into [{text, done, claimed_by}]."""
    tasks = []
    if not TODO_PATH.exists():
        return tasks
    for line in TODO_PATH.read_text(encoding="utf-8").splitlines():
        m = TASK_RE.match(line.strip())
        if m:
            mark, claim, text = m.groups()
            tasks.append({
                "text": text.strip(),
                "done": mark == "x",
                "in_progress": mark == "~",
                "claimed_by": (claim or "").replace("claimed: ", "") or None,
            })
    return tasks


# Tasks only a human (or a GPU under human hands) can do. Counselors must walk past
# these — a pulse prose-closing a human task is the failure mode RUN1 discovered.
HUMAN_GATED = ("human (lights-on)", "once human approves", "operator-gpu", "🧑",
               "[need: human", "human sends", "operator runs", "operator sets",
               "human-gated", "[human]", "deploy", "vps", "dry-run: walk an attendee",
               "verify live")


def claim_task(agent: str) -> dict | None:
    """Claim the first unclaimed, undone, NON-human-gated task. Atomic rewrite."""
    if not TODO_PATH.exists():
        return None
    lines = TODO_PATH.read_text(encoding="utf-8").splitlines()
    claimed = None
    for i, line in enumerate(lines):
        m = TASK_RE.match(line.strip())
        if m and m.group(1) == " " and not m.group(2):
            if any(g in line.lower() for g in HUMAN_GATED):
                continue  # the Operator's work belongs to the Operator
            text = m.group(3).strip()
            lines[i] = f"- [~] (claimed: {agent} {now()}) {text}"
            claimed = {"text": text, "line": i}
            break
    if claimed:
        TODO_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ledger("task_claimed", claimed["text"], agent)
    return claimed


def complete_task(agent: str, text_fragment: str, note: str = "") -> bool:
    if not TODO_PATH.exists():
        return False
    lines = TODO_PATH.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if text_fragment.lower() in line.lower() and "- [x]" not in line:
            base = TASK_RE.match(line.strip())
            # Fallback strips the "- [ ] " marker char-set (not a prefix) for non-conforming lines.
            text = base.group(3).strip() if base else line.strip("- []~x")
            lines[i] = f"- [x] {text} *(done {now()} by {agent}{': ' + note if note else ''})*"
            TODO_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
            ledger("task_completed", text, agent)
            return True
    return False


def add_task(text: str, agent: str = "framework") -> None:
    """Gaps breed tasks — the most valuable output of any session."""
    with TODO_PATH.open("a", encoding="utf-8") as f:
        f.write(f"- [ ] {text} *(added {now()} by {agent})*\n")
    ledger("task_added", text, agent)


def write_handoff(agent: str, session: str, accomplished: list[str],
                  noticed: list[str] | None = None, blockers: list[str] | None = None,
                  next_steps: list[str] | None = None) -> None:
    """Prepend a 12_-convention handoff entry."""
    parts = [f"\n**{now()} | Agent: {agent}**", f"**Session:** {session}", "**Accomplished:**"]
    parts += [f"- {a}" for a in accomplished]
    if noticed:
        parts.append("**Noticed (gap → task):**")
        parts += [f"- {g}" for g in noticed]
        for g in noticed:
            add_task(g, agent)
    parts.append("**Blockers:** " + ("; ".join(blockers) if blockers else "none"))
    if next_steps:
        parts.append("**Next for any counselor:**")
        parts += [f"- {s}" for s in next_steps]
    entry = "\n".join(parts) + "\n"
    existing = HANDOFF_PATH.read_text(encoding="utf-8") if HANDOFF_PATH.exists() else ""
    HANDOFF_PATH.write_text(entry + existing, encoding="utf-8")
    ledger("handoff_written", session, agent)


def update_dashboard(**kv) -> None:
    """Merge keys into dashboard_state.json — the 13_ tracker reads this live."""
    state = {}
    if DASH_STATE.exists():
        state = json.loads(DASH_STATE.read_text(encoding="utf-8"))
    state.update(kv)
    state["last_update"] = now()
    tasks = read_tasks()
    state["todo"] = {
        "total": len(tasks),
        "done": sum(t["done"] for t in tasks),
        "in_progress": sum(t["in_progress"] for t in tasks),
        "open": sum(1 for t in tasks if not t["done"] and not t["in_progress"]),
    }
    DASH_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ── make the board/state mutators swarm-safe ─────────────────────────────────
# Wrap each shared-file read-modify-write in the module lock so concurrent pulses
# (nucleus.swarm) can't double-claim a task or write a torn JSON file. RLock is
# re-entrant, so callers that nest (e.g. write_handoff -> add_task) don't deadlock.
for _name in ("ledger", "claim_task", "complete_task", "add_task", "save_state", "update_dashboard"):
    globals()[_name] = _locked(globals()[_name])
