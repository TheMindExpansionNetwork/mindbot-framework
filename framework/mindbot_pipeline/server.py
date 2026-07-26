"""SERVER — `mindbot serve`. The backend for MindBot OS (the wall-screen command center).

A stdlib-only HTTP server (no Flask, no deps) that does two jobs:
  1. serves the static front-ends (dashboard/, website/, apps/) from the repo root
  2. exposes a tiny JSON API that reads the LIVE files so the OS shows real state:
       /api/state      dashboard_state.json (last pulse, focus, counts)
       /api/board      open + in-progress tasks
       /api/ledger     recent ledger events (the book)
       /api/trails     recent ecosystem footprints
       /api/missions   mission catalog + progress
       /api/employees  the crew
       /api/commons    funded/used hours + witnesses
       /api/all        everything in one poll (what the OS uses)

Extend:
  - add a GET endpoint   -> write api_X() returning a dict, register it in ROUTES
  - add a POST action     -> write post_X(body) returning a dict, register it in POST_ROUTES
  - add a static file type -> add its suffix to the ctype map in do_GET
Every handler returns a plain dict (JSON-serialized by the router). It reads LIVE
files — no database, works offline, runs on a Pi.

Run:  python -m mindbot_pipeline.cli serve [--port 8080]   then open the printed URL.
"""

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .collaboration import COLLAB, LEDGER_PATH, ROOT, TODO_PATH, read_tasks

TRAILS = COLLAB / "trails.jsonl"
DASH = ROOT / "dashboard" / "dashboard_state.json"


def _jsonl_tail(path, n):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines()[-n:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def api_state():
    if DASH.exists():
        try:
            return json.loads(DASH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def api_board():
    tasks = read_tasks()
    return {"open": [t["text"] for t in tasks if not t["done"] and not t["in_progress"]][:12],
            "active": [t["text"] for t in tasks if t["in_progress"]][:8],
            "done_count": sum(t["done"] for t in tasks),
            "total": len(tasks)}


def api_ledger():
    return {"events": _jsonl_tail(LEDGER_PATH, 18)}


def api_trails():
    return {"trails": _jsonl_tail(TRAILS, 16)}


def api_missions():
    mp = COLLAB / "missions.json"
    if not mp.exists():
        mp = ROOT / "collaboration" / "missions.json"
    if not mp.exists():
        return {"missions": []}
    try:
        data = json.loads(mp.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"missions": []}
    todo = TODO_PATH.read_text(encoding="utf-8") if TODO_PATH.exists() else ""
    out = []
    for m in data.get("missions", []):
        total = len(m.get("tasks", []))
        # progress is inferred from the markdown todo: count checked lines tagged for
        # this mission. "\0" default = a tag that can never match (tagless missions -> 0).
        done = sum(1 for ln in todo.splitlines()
                   if m.get("tag", "\0") in ln and ln.strip().startswith("- [x]"))
        out.append({"name": m["name"], "done": min(done, total), "total": total,
                    "active": m.get("tag", "") in todo})
    return {"missions": out}


def api_employees():
    lore = ROOT / "lore"
    crew = []
    for f in sorted(lore.glob("*.md")) if lore.exists() else []:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"Employee #(\d+)", txt)
        if not m:
            continue
        glyph = (re.search(r"\*\*Glyph:\*\*\s*(\S+)", txt) or [None, "•"])[1]
        crew.append({"num": int(m.group(1)), "name": f.stem, "glyph": glyph})
    crew.sort(key=lambda c: c["num"])
    return {"employees": crew}


def api_commons():
    # balance is derived by replaying the whole ledger (9999 ≈ "all"); the commons is
    # the sum of fund/use hours recorded as ledger events, not a stored counter.
    funded = used = wit = 0
    for e in _jsonl_tail(LEDGER_PATH, 9999):
        if e.get("event") == "witnessed":
            wit += 1
        if e.get("event") == "commons_hour":
            mm = re.match(r"(fund|use)\s+(\d+)", e.get("detail", ""))
            if mm:
                if mm.group(1) == "fund":
                    funded += int(mm.group(2))
                else:
                    used += int(mm.group(2))
    return {"funded": funded, "used": used, "open": max(0, funded - used), "witnessed": wit}


def api_all():
    from . import __version__
    return {"version": __version__, "state": api_state(), "board": api_board(),
            "ledger": api_ledger()["events"], "trails": api_trails()["trails"],
            "missions": api_missions()["missions"], "employees": api_employees()["employees"],
            "commons": api_commons()}


def api_seats():
    """Full counselor detail — for the Control Deck's 'personalities' view."""
    from .counselors import COUNSELORS
    return {"seats": [{"name": n, "model": c["model"], "domain": c["domain"],
                       "likes": c["likes"], "dislikes": c["dislikes"], "role": c["role"]}
                      for n, c in COUNSELORS.items()]}


def api_outbox():
    """Drafts awaiting the Operator's approval (agent proposes, operator disposes)."""
    ob = ROOT / "framework" / "outbox"
    items = []
    for f in sorted(ob.glob("*.md"), key=lambda p: -p.stat().st_mtime)[:15] if ob.exists() else []:
        items.append({"name": f.name, "head": f.read_text(encoding="utf-8", errors="ignore").split("\n")[0][:80]})
    return {"outbox": items}


def api_fleet():
    """Live status of our Modal model fleet (S0N1C / c0d3r / v0x) — for the OS Fleet panel."""
    from .fleet import status
    return {"fleet": status()}


def api_commerce():
    """The earn/spend/operate panel: catalog, orders, and the compute-fund balance."""
    from .commerce import status
    return status()


def api_health():
    """Autonomous self-check over HTTP — for live monitoring of an unattended run."""
    from .nucleus import health
    return health()


def api_attest():
    """Proof-of-Autonomy attestation over HTTP — the verifiable compliance receipt."""
    from .provenance import attest
    return attest()


def api_budget():
    """Live spend vs the hard ceilings — the prevention half of the safety story."""
    from .budget import status
    return status()


def api_mods():
    """Installed extensions + the capabilities each one declared."""
    from .mods import discover
    return {"mods": [{k: v for k, v in m.items() if k != "doc"} for m in discover()]}


def api_notary():
    """Anchor history: has today's ledger drifted from anything we published?"""
    from .notary import audit
    return audit()


def api_whoami():
    """The system's self-model — purpose, charter, real capabilities, history, and LIMITS."""
    from .identity import whoami
    return whoami()


def api_setup():
    """Is this install ready to work? Drives the onboarding screen.

    NEVER returns the key itself — only whether one is present, plus its harmless tail so a
    user can tell WHICH key is installed without exposing it.
    """
    import os as _os
    from .budget import caps
    key = _os.environ.get("OPENROUTER_API_KEY", "")
    return {
        "configured": bool(key),
        "key_tail": ("…" + key[-6:]) if key else None,
        "model": _os.environ.get("MINDBOT_MODEL", "") or None,
        "free_mode": _os.environ.get("MINDBOT_FREE") == "1",
        "budget": {k: caps()[k] for k in ("run", "day", "total")},
        "budget_enforced": caps()["enabled"],
    }


ROUTES = {"state": api_state, "board": api_board, "ledger": api_ledger, "trails": api_trails,
          "missions": api_missions, "employees": api_employees, "commons": api_commons,
          "seats": api_seats, "outbox": api_outbox, "fleet": api_fleet,
          "commerce": api_commerce, "health": api_health, "attest": api_attest,
          "budget": api_budget, "mods": api_mods, "notary": api_notary,
          "setup": api_setup, "whoami": api_whoami, "all": api_all}


def post_run(body):
    """Operate the hive from the Control Deck. Runs ONE action; drafts stay in outbox."""
    cmd = body.get("cmd", "")
    if cmd == "pulse":
        from .nucleus import pulse
        return pulse()
    if cmd == "yolo":
        from .nucleus import yolo
        return yolo(max_rounds=int(body.get("rounds", 5)))
    if cmd == "meeting":
        from .nucleus import meeting
        return {"minutes": meeting(body.get("topic", "what to build next"))}
    return {"error": f"unknown cmd: {cmd}"}


def post_chat(body):
    """Chat with one counselor (Control Deck). Reply is conversational; drafts never send."""
    from .counselors import COUNSELORS, persona_prompt
    from .models import llm, strip_reasoning
    seat = body.get("seat", "Mind")
    c = COUNSELORS.get(seat, COUNSELORS["Mind"])
    sysp = persona_prompt(seat) + " LIVE chat at the switchboard: 2-5 sentences, in voice, no tags."
    text, mode = llm(c["provider"], c["model"], sysp, body.get("text", "hello"))
    return {"seat": seat, "reply": strip_reasoning(text)[:900], "mode": mode}


def post_setup(body):
    """BRING-YOUR-OWN-KEY. Validate an OpenRouter key live, then persist it to framework/.env.

    This is the whole onboarding story: a new user opens the console, pastes a key, and the
    agent works. No file editing, no shell. The key is LIVE-VALIDATED before it is saved, so a
    typo fails here rather than silently degrading every later run to template mode.

    The key is written ONLY to framework/.env (gitignored) and never echoed back to the browser.
    """
    key = (body.get("key") or "").strip()
    if not key:
        return {"ok": False, "error": "no key provided"}
    if not key.startswith("sk-or-"):
        return {"ok": False, "error": "that does not look like an OpenRouter key (expected sk-or-…)"}
    from .models import validate_key, write_env_key
    ok, msg = validate_key("openrouter", key)
    if not ok:
        return {"ok": False, "error": f"OpenRouter rejected the key: {msg}"}
    write_env_key("OPENROUTER_API_KEY", key)
    # optional extras the setup screen can send along
    model = (body.get("model") or "").strip()
    if model:
        write_env_key("MINDBOT_MODEL", model)
    cap = str(body.get("day_cap") or "").strip()
    if cap:
        write_env_key("MINDBOT_BUDGET_DAY", cap)
    from .collaboration import ledger
    ledger("setup_key_saved", f"openrouter key validated + saved (model={model or 'per-seat'})", "setup")
    return {"ok": True, "message": "key validated and saved", "model": model or None,
            "day_cap": cap or None}


def post_config(body):
    """Non-secret settings from the UI (model pin, budget ceiling). Never touches the key."""
    from .models import write_env_key
    import os as _os
    changed = {}
    if "model" in body:
        v = str(body["model"]).strip()
        write_env_key("MINDBOT_MODEL", v)
        _os.environ["MINDBOT_MODEL"] = v
        changed["model"] = v or "(cleared — per-seat defaults)"
    if "day_cap" in body:
        v = str(body["day_cap"]).strip()
        write_env_key("MINDBOT_BUDGET_DAY", v)
        _os.environ["MINDBOT_BUDGET_DAY"] = v
        changed["day_cap"] = v
    return {"ok": True, "changed": changed}


POST_ROUTES = {"run": post_run, "chat": post_chat, "setup": post_setup, "config": post_config}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet — the OS is the log
        pass

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode("utf-8"))

    def do_POST(self):
        path = self.path.split("?")[0]
        if path.startswith("/api/"):
            fn = POST_ROUTES.get(path[5:])
            if fn:
                try:
                    ln = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(ln) or b"{}")
                    return self._send(200, json.dumps(fn(body)))
                except Exception as e:  # noqa: BLE001
                    return self._send(200, json.dumps({"error": str(e)}))
        return self._send(404, json.dumps({"error": "no such endpoint"}))

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            path = "/dashboard/center.html"
        if path.startswith("/api/"):
            fn = ROUTES.get(path[5:])
            if fn:
                try:
                    return self._send(200, json.dumps(fn()))
                except Exception as e:  # noqa: BLE001 — API must not 500 the wall screen
                    return self._send(200, json.dumps({"error": str(e)}))
            return self._send(404, json.dumps({"error": "no such endpoint"}))
        # static files (jailed to repo root) — resolve() then prefix-check defeats
        # ../ traversal; never serve a path that escapes ROOT.
        target = (ROOT / path.lstrip("/")).resolve()
        if not str(target).startswith(str(ROOT.resolve())) or not target.is_file():
            return self._send(404, "not found", "text/plain")
        ctype = {".html": "text/html", ".css": "text/css", ".js": "application/javascript",
                 ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png",
                 ".mp4": "video/mp4", ".wav": "audio/wav"}.get(target.suffix, "text/plain")
        return self._send(200, target.read_bytes(), ctype)


def serve(port=8080):
    srv = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    print(f"\n  MindBot OS serving → http://localhost:{port}/   (Ctrl-C to stop)")
    print(f"  API: http://localhost:{port}/api/all\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  MindBot OS down. The ledger holds. 🌒")
