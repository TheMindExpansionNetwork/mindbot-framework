"""The fleet — one source of truth for our own models on Modal, + a live status ping.

Each pod is a callsign bound to an env var holding its URL. `mindbot fleet` and the
MindBot OS interface read this. Stdlib only (urllib), so it runs anywhere.

A pod that's scaled to zero answers slowly on the first hit — we report that honestly as
"asleep" (it's not down; it wakes on the next real request). Idle pods cost $0.

Extend: add a pod -> append a callsign entry to FLEET (env = the .env var holding its URL,
kind = "openai" for an OpenAI-shaped server else "tts"); the router (models.py) and the
`mindbot fleet` command pick it up automatically. New server shape -> add a branch in _probe.
"""

import os
import urllib.request

# callsign -> config. env = the .env var holding the pod's URL (…/v1 for openai kind).
FLEET = {
    "S0N1C": {"env": "MINDBOT_SONIC_URL", "model": "DiffusionGemma-26B-A4B",
              "kind": "openai", "gpu": "A100-80GB", "desc": "diffusion swarm (fast parallel)"},
    "c0d3r": {"env": "MINDBOT_CODER_URL", "model": "Qwen2.5-Coder-7B",
              "kind": "openai", "gpu": "L4", "desc": "agentic coding brain"},
    "v0x":   {"env": "MINDBOT_VOXX_URL", "model": "Kokoro-82M (Higgs v3 queued)",
              "kind": "tts", "gpu": "CPU", "desc": "voice / narration"},
}

_TIMEOUT = 4   # short: a sleeping pod should read "asleep", not hang the table


def url_for(callsign: str) -> str:
    """The configured URL for a pod, or '' if its env var isn't set."""
    cfg = FLEET.get(callsign, {})
    return os.environ.get(cfg.get("env", ""), "").strip()


def _probe(base: str, kind: str) -> str:
    """Return 'live' | 'asleep' | 'error'. Never raises."""
    import urllib.error
    if kind == "openai":
        root = base.rstrip("/")
        root = root[:-3] if root.endswith("/v1") else root
        target = root + "/v1/models"
        method = "GET"
    else:  # tts / other: just see if the host answers at all
        target = base.rstrip("/")
        method = "GET"
    try:
        req = urllib.request.Request(target, method=method)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return "live" if r.status < 500 else "asleep"
    except urllib.error.HTTPError as e:
        # a response (even 4xx) means the server is up and serving
        return "live" if e.code < 500 else "asleep"
    except Exception:  # noqa: BLE001 — timeout / refused = cold (scaled to zero) or down
        return "asleep"


def status(probe: bool = True) -> list[dict]:
    """Snapshot of the fleet: callsign, model, gpu, url-set?, and (optionally) live state."""
    out = []
    for cs, cfg in FLEET.items():
        u = url_for(cs)
        row = {"callsign": cs, "model": cfg["model"], "gpu": cfg["gpu"],
               "desc": cfg["desc"], "url": u, "state": "unset" if not u else "?"}
        if u and probe:
            row["state"] = _probe(u, cfg["kind"])
        out.append(row)
    return out
