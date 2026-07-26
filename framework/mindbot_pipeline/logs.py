"""Operational logging — the trace an unattended autonomous run leaves behind.

Distinct from the ledger (collaboration.ledger), which records WHAT happened — honestly, for
humans, append-only. THIS is the HOW: debug detail, model latency, and especially ERRORS, so a
swarm or yolo loop running for hours with no human watching is observable AFTER the fact.

Stdlib `logging` only (the 2045 rule). Rotating file so it never grows unbounded. INFO by
default; set MINDBOT_DEBUG=1 for DEBUG + console echo. Logs live in mindbot_pipeline/logs/.

Extend: anywhere in the framework, `from .logs import get_logger; log = get_logger("name")`
and call log.info/.warning/.exception. To add a sink (e.g. an alert webhook), add a handler in
_configure(). recent_errors() powers `mindbot health`, so keep WARNING/ERROR levels meaningful.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOG_DIR / "mindbot.log"
_CONFIGURED = False


def _configure() -> None:
    """Set up the root 'mindbot' logger exactly once (idempotent, never raises)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True
    root = logging.getLogger("mindbot")
    level = logging.DEBUG if os.environ.get("MINDBOT_DEBUG") else logging.INFO
    root.setLevel(level)
    root.propagate = False
    fmt = logging.Formatter("%(asctime)s %(levelname)-5s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        fh.setLevel(level)
        root.addHandler(fh)
    except Exception:  # noqa: BLE001 — never let logging setup crash the agent
        pass
    if os.environ.get("MINDBOT_DEBUG"):
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)


def get_logger(name: str = "core") -> logging.Logger:
    """A child logger under 'mindbot.<name>'. Cheap to call; configures on first use."""
    _configure()
    return logging.getLogger(f"mindbot.{name}")


def recent_errors(n: int = 10) -> list[str]:
    """Tail the last N WARNING/ERROR lines from the log — for `mindbot health`."""
    if not LOG_FILE.exists():
        return []
    try:
        lines = LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:  # noqa: BLE001
        return []
    hits = [ln for ln in lines if " ERROR " in ln or " WARNING" in ln]
    return hits[-n:]
