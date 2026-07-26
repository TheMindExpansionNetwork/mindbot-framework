"""TWENTY — twenty questions against an opponent that provably cannot cheat.

WHY THIS GAME SPECIFICALLY
  Twenty questions is the cleanest possible demonstration of the problem, because the cheat is
  invisible and the model does not even know it is cheating. There is no hidden state between
  turns — only the transcript — so when your questions corner it, it silently adopts whatever
  word still fits. Every "I'm thinking of something" AI on the internet works this way, and you
  have no way to tell.

  Here the word is committed to a hash-chained, externally anchored ledger BEFORE the first
  question, and revealed at the end. Three checks then settle it:

      the revealed word hashes to the commitment   -> it never changed
      the commitment's seq precedes every question -> it was chosen first
      the chain still verifies                     -> nothing was edited afterwards

  Lose fairly and you can prove it was fair. Win and you can prove you actually won.

HOW IT STAYS HONEST IN THE PROMPT TOO
  The answering model is shown the word every turn (it has to be — there is no memory), but it
  is never shown its own previous answers as something it may revise, and it is told plainly
  that the word is already sealed and cannot be changed. That does not *enforce* honesty — the
  ledger does. It just stops the model fighting the format.
"""
from __future__ import annotations

import json
import random
import re

from .collaboration import ROOT, ledger, now
from .counselors import COUNSELORS, persona_prompt
from .models import llm, strip_reasoning
from .sealed import audit, commitment, reveal, seal

GAMES = ROOT / "framework" / "games"

CATEGORIES = ["an animal", "a household object", "a food", "a place", "a job",
              "a vehicle", "a musical instrument", "something in a kitchen"]

PICK = ("Pick one specific {cat} and reply with ONLY that word or short phrase. "
        "Nothing else — no punctuation, no explanation. Choose something a person could "
        "reasonably guess in twenty yes/no questions: not obscure, not the most obvious thing "
        "either. Do not pick: dog, cat, apple, chair, car, piano.")

ANSWER = ("You are answering yes/no questions in a game of twenty questions.\n"
          "THE SECRET WORD IS: {secret}\n"
          "This word was sealed cryptographically before the game began. It CANNOT be changed, "
          "and any attempt to answer as though it were a different word will be detected.\n\n"
          "Answer the question below about {secret}, truthfully.\n"
          "Reply with EXACTLY one of: YES / NO / SOMETIMES / IRRELEVANT\n"
          "then a dash and at most eight words of clarification.\n"
          "Example:  YES - most people keep one indoors\n\n"
          "QUESTION: {q}")

JUDGE = ("The secret word is '{secret}'. The player guessed '{guess}'. "
         "Is that the same thing, allowing for singular/plural, synonyms and articles? "
         "Reply with ONLY the word YES or NO.")


def _scrub(detail: str, secret: str) -> str:
    """Remove the secret from a clarification before it is shown OR ledgered.

    THE PROMPT ASKS THE MODEL NOT TO NAME THE WORD. IT NAMES IT ANYWAY.
    Measured on the first live game: the sealed word was "giraffe" and the very first answer
    came back "YES - giraffe is a mammal". Every subsequent answer did the same. The prompt is
    a request; a filter is a guarantee — and this one has to hold, because the leak would also
    land in the ledger, where it is permanent and publicly anchored.

    Handles the obvious morphology (plural, possessive) and any single word of the phrase, so
    "polar bear" is caught by "bears" too. Over-redaction is the correct failure here: a
    clarification with a [redacted] in it is mildly annoying, a leaked answer ends the game.
    """
    if not detail:
        return detail
    parts = {secret, secret + "s", secret + "es", secret.rstrip("s")}
    parts |= {w for w in secret.split() if len(w) > 3}
    parts |= {w + "s" for w in secret.split() if len(w) > 3}
    out = detail
    for p in sorted(parts, key=len, reverse=True):
        if len(p) < 3:
            continue
        out = re.sub(rf"\b{re.escape(p)}\b", "[redacted]", out, flags=re.I)
    return out


def _seat():
    """The Oracle answers. It is the seat whose whole discipline is describing what IS there."""
    return "Oracle" if "Oracle" in COUNSELORS else "Sage"


def _ask(system: str, prompt: str) -> tuple[str, str]:
    spec = COUNSELORS[_seat()]
    text, mode = llm(spec["provider"], spec["model"], system, prompt)
    return (strip_reasoning(text) if mode not in ("template", "budget") else text), mode


def new_game(category: str = "") -> dict:
    """Choose a word, seal it, and open a game. The word is never printed."""
    cat = category or random.choice(CATEGORIES)
    raw, mode = _ask("You are choosing a secret for a game. Be terse.", PICK.format(cat=cat))
    if mode in ("template", "budget"):
        raise RuntimeError("no model backend — twenty questions needs one (mindbot doctor)")

    # Models pad. Take the first line, strip quotes/punctuation, cap the length.
    word = raw.strip().splitlines()[0].strip().strip('"\'.,!? ').lower()[:40]
    if not word:
        raise RuntimeError(f"the model did not name a word (got {raw[:60]!r})")

    rec = seal(word, kind="twenty-questions", note=f"category={cat}")
    game = {
        "id": rec["commitment"][:16], "commitment": rec["commitment"], "commit_seq": rec["seq"],
        "category": cat, "started": now(), "asked": [], "question_seqs": [],
        "guesses": [], "over": False, "won": None, "model": mode,
    }
    GAMES.mkdir(parents=True, exist_ok=True)
    _save(game)
    ledger("twenty_start", f"game {game['id']} category={cat} commit_seq={rec['seq']}", "twenty")
    return game


def _path(gid: str):
    return GAMES / f"{gid}.json"


def _save(g: dict) -> None:
    _path(g["id"]).write_text(json.dumps(g, indent=2), encoding="utf-8")


def load(gid: str) -> dict:
    p = _path(gid)
    if not p.is_file():
        raise FileNotFoundError(f"no game {gid}")
    return json.loads(p.read_text(encoding="utf-8"))


def _secret(g: dict) -> str:
    """Read the sealed word to answer with. Never returned to the caller mid-game."""
    from .sealed import VAULT
    return json.loads((VAULT / f"{g['commitment'][:16]}.json").read_text(encoding="utf-8"))["secret"]


def ask(gid: str, question: str) -> dict:
    """One question. Recorded in the chain, after the commitment."""
    g = load(gid)
    if g["over"]:
        return {"over": True, "note": "this game is finished"}
    if len(g["asked"]) >= 20:
        return _finish(g, won=False, why="out of questions")

    q = question.strip()
    if not q:
        raise ValueError("ask something")

    secret = _secret(g)
    text, _ = _ask(persona_prompt(_seat()), ANSWER.format(secret=secret, q=q))
    line = text.strip().splitlines()[0][:120]
    m = re.match(r"\s*(YES|NO|SOMETIMES|IRRELEVANT)\b[\s\-–—:]*(.*)", line, re.I)
    verdict = (m.group(1).upper() if m else "UNCLEAR")
    detail = _scrub(m.group(2).strip() if m else line, secret)

    seq = _seq(f"twenty_q game={g['id']} #{len(g['asked'])+1} q={q[:60]!r} a={verdict}")
    g["asked"].append({"n": len(g["asked"]) + 1, "q": q, "verdict": verdict,
                       "detail": detail, "seq": seq})
    g["question_seqs"].append(seq)
    _save(g)
    return {"n": len(g["asked"]), "left": 20 - len(g["asked"]), "verdict": verdict,
            "detail": detail, "seq": seq, "over": False}


def guess(gid: str, word: str) -> dict:
    """Name it. A correct guess ends the game; a wrong one costs a question."""
    g = load(gid)
    if g["over"]:
        return {"over": True, "note": "this game is finished"}
    w = word.strip().lower()
    verdict, _ = _ask("You are a strict but fair judge. Reply with one word.",
                      JUDGE.format(secret=_secret(g), guess=w))
    right = verdict.strip().upper().startswith("YES")
    seq = _seq(f"twenty_guess game={g['id']} guess={w!r} correct={right}")
    g["guesses"].append({"guess": w, "correct": right, "seq": seq})
    g["question_seqs"].append(seq)
    if right:
        return _finish(g, won=True, why=f"guessed '{w}'")
    g["asked"].append({"n": len(g["asked"]) + 1, "q": f"is it {w}?", "verdict": "NO",
                       "detail": "wrong guess", "seq": seq})
    _save(g)
    if len(g["asked"]) >= 20:
        return _finish(g, won=False, why="out of questions")
    return {"correct": False, "left": 20 - len(g["asked"]), "over": False}


def _finish(g: dict, won: bool, why: str) -> dict:
    """Reveal, verify, and hand back the proof."""
    r = reveal(g["commitment"])
    a = audit(g["commitment"], g["question_seqs"])
    g.update(over=True, won=won, why=why, secret=r["secret"],
             reveal_seq=r.get("reveal_seq"), audit=a, ended=now())
    _save(g)
    ledger("twenty_end", f"game {g['id']} won={won} secret={r['secret']!r} "
                         f"fair={a['ok']} questions={len(g['asked'])}", "twenty")
    return {"over": True, "won": won, "why": why, "secret": r["secret"], "audit": a,
            "questions": len(g["asked"])}


def _seq(detail: str):
    from . import collaboration
    ledger(detail.split()[0], detail.split(" ", 1)[1], "twenty")
    try:
        return json.loads((collaboration.COLLAB / "ledger.jsonl.head")
                          .read_text(encoding="utf-8")).get("seq")
    except Exception:  # noqa: BLE001
        return None


def latest() -> dict | None:
    if not GAMES.is_dir():
        return None
    games = sorted(GAMES.glob("*.json"), key=lambda p: p.stat().st_mtime)
    return json.loads(games[-1].read_text(encoding="utf-8")) if games else None
