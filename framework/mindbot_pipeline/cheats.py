"""CHEATS — the degenerate menu. Konami the council, summon a rave, ask the oracle, flex trophies.

All cosmetic terminal fun, stdlib + ANSI. The constitution still rides along: nothing here
transmits, charges, or escapes the terminal. Pure vibes for the Operator. 🌒

Pure helpers (menu_text / rave_frame / oracle / trophies) return strings/data so they unit-test
without animation; the thin animated wrappers (rave) just print them on a loop.

Extend: add a cheat code -> add an entry to CHEATS (handled by apply/menu_text); add an
8-ball reply -> append to _8BALL; add an achievement -> append to `defs` in trophies()
keyed on a real ledger event (the event must be written elsewhere, e.g. collaboration.ledger).
"""
import os
import time

os.system("")  # enable ANSI on Windows consoles

R, B, DIM = "\033[0m", "\033[1m", "\033[2m"
NEON = ["\033[38;5;201m", "\033[38;5;51m", "\033[38;5;48m",
        "\033[38;5;226m", "\033[38;5;141m", "\033[38;5;214m"]

# code -> (what it says, optional "go" hint). Some unlock vibes, some just wink.
CHEATS = {
    "konami":        ("⇧⇧⇩⇩⇦⇨⇦⇨BA — 30 lives for the collective. CULTURE CONFIRMED. 😎", ""),
    "iddqd":         ("GODMODE — Operator clearance: MAX. (you always had it. that's the point.)", ""),
    "idkfa":         ("full keys + all the models. set your .env and it's literally true.", "mindbot auth"),
    "hesoyam":       ("full health, armor, +$250k compute. (cosmetic, degenerate.)", "mindbot trophies"),
    "leeroy":        ("LEEEEROY JENKIIINS — max chaos, never stops.", "mindbot yolo"),
    "swarmlord":     ("the WHOLE council, at once. eleven minds, one board.", "mindbot swarm --workers 11"),
    "thereisnospoon":("there is no board. only tasks. theme → matrix.", "mindbot play"),
    "moneyprinter":  ("brrrrr 💸 — opens the shop. (still needs a Stripe key, you degenerate.)", "mindbot commerce --store"),
    "rave":          ("the terminal becomes a dancefloor.", "mindbot rave"),
    "420":           ("Spark blazes up. Glow the firefly approves. 🔥✨", ""),
    "2045":          ("countdown engaged. the festival remembers your name.", ""),
    "freemymind":    ("there is a difference between knowing the path and walking it, Operator.", ""),
    "bigredbutton":  ("you found it. it does nothing. (the constitution thanks you.)", ""),
}

_BANNER = r"""
   __  __ ___ _  _ ___  ___  ___ _____ ____
  |  \/  |_ _| \| |   \| _ )/ _ \_   _|_  /
  | |\/| || || .` | |) | _ \ (_) || |  / /
  |_|  |_|___|_|\_|___/|___/\___/ |_| /___|   ✦ cheat menu ✦
"""


def menu_text() -> str:
    """The whole cheat sheet as a string (so it tests + prints the same)."""
    lines = [f"{NEON[4]}{_BANNER}{R}",
             f"  {DIM}type:  mindbot cheat <code>   ·   all cosmetic, nothing transmits{R}", ""]
    for code, (blurb, go) in CHEATS.items():
        tail = f"   {DIM}→ {go}{R}" if go else ""
        lines.append(f"  {NEON[1]}{code:<14}{R} {blurb}{tail}")
    lines += ["", f"  {DIM}secret: there are more. the council never tells everything. 👁{R}", ""]
    return "\n".join(lines)


def apply(code: str) -> str:
    """Trigger a cheat by code. Returns the blurb (+ a 'go' hint). Unknown → a wink."""
    code = (code or "").lower().strip().replace(" ", "")
    # alias the typed-out Konami sequences to the canonical key in CHEATS
    if code in ("uuddlrlrba", "upupdowndownleftrightleftrightba"):
        code = "konami"
    if code not in CHEATS:
        return f"  {DIM}'{code}' — not a code the council knows. try: mindbot cheat{R}"
    blurb, go = CHEATS[code]
    out = f"\n  {NEON[3]}✦ {code}{R}\n  {blurb}\n"
    if go:
        out += f"  {DIM}→ {go}{R}\n"
    return out


def rave_frame(t: int) -> str:
    """One frame of the terminal rave — a band of strobing neon blocks."""
    width = 38
    row = "".join(NEON[(t + i) % len(NEON)] + "█" for i in range(width)) + R
    word = "  ".join(NEON[(t + i) % len(NEON)] + c + R for i, c in enumerate("M1NDB0TZ"))
    return f"{row}\n        {word}\n{row}"


def rave(cycles: int = 24, delay: float = 0.08) -> None:
    """Time-boxed terminal light show. ESC is for cowards; it ends on its own. 🪩"""
    try:
        for t in range(cycles):
            print("\033[H\033[2J", end="")  # clear
            print("\n\n" + rave_frame(t))
            print(f"\n        {DIM}🪩 the eclipse drops the beat · {cycles - t} …{R}")
            time.sleep(delay)
    except KeyboardInterrupt:
        pass
    print(R + "\n        the lights come up. the work remains. 🌒\n")


_8BALL = [
    "the eclipse says: yes. obviously.", "the council leans no.", "ship it. 🚀",
    "ask again after a pulse.", "the ledger is unsure, but hopeful.",
    "Oracle squints… signs point to yes.", "absolutely not, degenerate.",
    "the swarm has already decided. you'll see.", "do it for the lore.",
    "Tempest warns: edge case ahead.", "Sage nods slowly. proceed.",
    "the answer was in the outbox the whole time.", "🔮 hazy… try a real model.",
    "yes, but draft it first — a human sends.", "the festival approves.",
]


def oracle(question: str) -> str:
    """Magic 8-ball, council flavor. Deterministic per question (no RNG — resume-safe + testable)."""
    q = (question or "").strip()
    pick = _8BALL[sum(ord(c) for c in q) % len(_8BALL)] if q else "ask me something, Operator."
    return f"\n  👁  {NEON[4]}{q or '(silence)'}{R}\n      {pick}\n"


# ── TROPHIES — achievements unlocked by the swarm's REAL progress ─────────────
def _ledger_events() -> set:
    from .collaboration import LEDGER_PATH
    import json
    evs = set()
    if LEDGER_PATH.exists():
        for ln in LEDGER_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                evs.add(json.loads(ln).get("event", ""))
            except Exception:  # noqa: BLE001
                pass
    return evs


def trophies() -> list:
    """Compute the trophy case from real state — returns [(name, unlocked, hint)]."""
    from .collaboration import load_state
    try:
        pulses = load_state().get("pulses", 0)
    except Exception:  # noqa: BLE001
        pulses = 0
    evs = _ledger_events()  # event names that have actually been written to the ledger
    try:
        # every cross-module read is wrapped: a missing/empty state must never crash the case
        from . import commerce
        sold = commerce.compute_fund()["sales"] > 0
    except Exception:  # noqa: BLE001
        sold = False
    # (name, unlocked, how-to-earn)
    defs = [
        ("🌱 First Breath",     pulses >= 1,                 "run one pulse"),
        ("💯 Centurion",        pulses >= 100,               "100 pulses"),
        ("🐝 Hive Mind",        "swarm_launch" in evs,       "launch a swarm"),
        ("🛸 Self-Driving",     "autopilot_done" in evs,     "run mindbot autopilot"),
        ("🤖 Never Stops",      "yolo_start" in evs,         "run mindbot yolo"),
        ("🗳 Council Convened",  "meeting" in evs,            "hold a council meeting"),
        ("💸 First Blood",      sold or "sale_recorded" in evs, "record a sale"),
        ("🔗 Cha-Ching",        any(e.startswith("paylink") for e in evs), "create a Stripe link"),
        ("🏪 Shopkeeper",       "store_built" in evs,        "mindbot commerce --store"),
        ("📜 The Honest Book",  "task_completed" in evs,     "complete a task → ledger"),
        ("🌒 2045 Believer",    True,                        "just be here"),
    ]
    return [(n, bool(u), h) for n, u, h in defs]


def trophies_text() -> str:
    rows = trophies()
    got = sum(1 for _, u, _ in rows if u)
    lines = [f"\n  {NEON[5]}🏆 TROPHY CASE{R}  {DIM}{got}/{len(rows)} unlocked{R}\n"]
    for name, unlocked, hint in rows:
        if unlocked:
            lines.append(f"   {NEON[2]}✔{R} {name}")
        else:
            lines.append(f"   {DIM}✗ {name}  ·  {hint}{R}")
    lines.append("")
    return "\n".join(lines)
