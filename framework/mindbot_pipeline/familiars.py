"""FAMILIARS — every counselor's silent runner. They don't talk. They fetch.

A familiar is the context-retrieval layer wearing fur: before a seat answers,
its familiar runs into the workspace and comes back with REAL data (board state,
ledger lines, dataset stats, memory hits). The counselor thinks; the familiar
carries. Every run leaves a track in trails.jsonl — the ecosystem's footprints.

Nobody has named this pattern before: context-fetching familiars. Now it's named.

Extend: give a seat a familiar -> add an entry to FAMILIARS (key = counselor
seat name, must match the seats elsewhere in the pipeline). Teach familiars a new
data source -> add a private _fetcher() and wire a keyword branch into fetch().
"""

import datetime
import json

from .collaboration import COLLAB, LEDGER_PATH, TODO_PATH, read_tasks
from .stages import DATASET_MANIFEST

TRAILS = COLLAB / "trails.jsonl"

FAMILIARS = {
    "Sage":     {"name": "Moss",    "glyph": "🐢", "kind": "an old tortoise",
                 "quirk": "moves slow, never wrong, has seen every plan before"},
    "Forge":    {"name": "Socket",  "glyph": "🐦", "kind": "a magpie",
                 "quirk": "steals shiny bolts and perfect function names"},
    "Scribe":   {"name": "Dot",     "glyph": "🦋", "kind": "an ink-moth",
                 "quirk": "lands only on typos; flutters hard near passive voice"},
    "Vanguard": {"name": "Nitro",   "glyph": "🐿", "kind": "a caffeinated squirrel",
                 "quirk": "already left before you finished the sentence"},
    "Quantum":  {"name": "Bit",     "glyph": "🐤", "kind": "a hummingbird",
                 "quirk": "counts its own wingbeats; disapproves of estimates"},
    "Seeker":   {"name": "Truffle", "glyph": "🐕", "kind": "a bloodhound puppy",
                 "quirk": "finds what you needed, plus three things you didn't ask for"},
    "Spark":    {"name": "Glow",    "glyph": "✨", "kind": "a firefly",
                 "quirk": "extremely chill. blinks in lowercase. vibes are data"},
    "Oracle":   {"name": "Echo",    "glyph": "🦉", "kind": "a pocket owl",
                 "quirk": "stares at the 2045 countdown like it's the weather"},
    "Titan":    {"name": "Boulder", "glyph": "🪲", "kind": "a pillbug",
                 "quirk": "carries fifty times its weight; has never commented"},
    "Tempest":  {"name": "Zephyr",  "glyph": "🪁", "kind": "a paper kite",
                 "quirk": "arrives with eleven ideas, leaves with your pen"},
    "Mind":     {"name": "Lumen",   "glyph": "🌒", "kind": "an eclipse-moth",
                 "quirk": "born from the dream log; navigates by the ledger's light"},
}


def track(actor: str, glyph: str, action: str, detail: str = "") -> None:
    """Leave a footprint. The ecosystem is visible because everyone leaves tracks."""
    TRAILS.parent.mkdir(parents=True, exist_ok=True)
    with TRAILS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "actor": actor, "glyph": glyph, "action": action, "detail": detail[:160],
        }, ensure_ascii=False) + "\n")


def _board():
    tasks = read_tasks()
    open_t = [t["text"][:70] for t in tasks if not t["done"] and not t["in_progress"]]
    return f"{len(open_t)} unclaimed tasks; top: " + " | ".join(open_t[:3])


def _ledger_tail(n=4):
    if not LEDGER_PATH.exists():
        return "ledger empty"
    lines = LEDGER_PATH.read_text(encoding="utf-8").splitlines()[-n:]
    out = []
    for line in lines:
        try:
            e = json.loads(line)
            out.append(f"{e['ts']} {e['event']}: {e['detail'][:60]}")
        except json.JSONDecodeError:
            continue  # tolerate a half-written/corrupt ledger line, keep the rest
    return "; ".join(out)


def _dataset():
    if not DATASET_MANIFEST.exists():
        return "no dataset manifest"
    m = json.loads(DATASET_MANIFEST.read_text(encoding="utf-8"))
    return (f"corpus {m['total']} train/{m['validation']}/{m['test']} splits, "
            f"{m.get('gold_seeds_heldout', '?')} gold seeds held out")


def _recall(word):
    hits = []
    for path in (COLLAB / "AGENT_HANDOFF_NOTES.md", TODO_PATH):
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if word.lower() in line.lower():
                    hits.append(line.strip()[:90])
                if len(hits) >= 3:  # cap recall: 3 scent-hits is enough context
                    return "; ".join(hits)
    return "; ".join(hits) if hits else f"no scent of '{word}'"


def fetch(seat: str, message: str) -> tuple[str, str]:
    """The familiar runs. Returns (action_line_for_ui, context_for_prompt).

    Keyword-routed to REAL data — this is live context injection, not theater.
    """
    fam = FAMILIARS.get(seat, FAMILIARS["Sage"])  # unknown seat -> Sage's familiar
    m = message.lower()
    # First matching keyword branch wins; order = priority. New sources go above
    # the else so they can intercept before the generic _recall fallback.
    if any(w in m for w in ("task", "todo", "board", "work on", "build", "next")):
        ctx = _board()
        act = f"{fam['glyph']} {fam['name']} darts to the board → {ctx.split(';')[0]}"
    elif any(w in m for w in ("money", "dollar", "ledger", "gig", "paid", "history", "happened")):
        ctx = _ledger_tail()
        act = f"{fam['glyph']} {fam['name']} drags back the ledger's last pages"
    elif any(w in m for w in ("dataset", "train", "corpus", "gold", "model")):
        ctx = _dataset()
        act = f"{fam['glyph']} {fam['name']} returns dusted in dataset stats"
    else:
        # No keyword hit: grep memory for the first "meaty" word (>5 chars),
        # else fall back to the board so the seat never answers context-blind.
        words = [w for w in m.split() if len(w) > 5]
        ctx = _recall(words[0]) if words else _board()
        act = f"{fam['glyph']} {fam['name']} sniffs the archives…"
    track(fam["name"], fam["glyph"], f"ran for {seat}", ctx[:100])
    return act, ctx


def trails_tail(n=20):
    if not TRAILS.exists():
        return []
    out = []
    for line in TRAILS.read_text(encoding="utf-8").splitlines()[-n:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
