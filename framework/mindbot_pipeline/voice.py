"""VOICE — eleven characters, one throat.

WHAT THIS COMPLETES
      eyes   Inkling on Modal      images in            self-hosted, fixed cost
      ears   Inkling on Modal      audio in             self-hosted, fixed cost
      voice  Inflect-Nano-v2       text out as speech   LOCAL, CPU, $0

  `owensong/Inflect-Nano-v2`: 3.97M params, 15.97 MB on disk, Apache-2.0, ~10.7x realtime on
  four CPU threads. On a 6-vCPU VPS that is a rounding error — it will not fight a browser
  worker for resources, which is the constraint that rules out most local TTS.

TWO ENGINES, AND WHY BOTH ARE HERE

  KOKORO (default) — `hexgrad/Kokoro-82M`, 82M params, Apache-2.0, 24 kHz, **54 voices** across
  8 languages (28 English). Each counselor gets a GENUINELY different speaker: different
  gender, different accent, different timbre. This is what you want.

  INFLECT (fallback) — `owensong/Inflect-Nano-v2`, 3.97M params, **15.97 MB**, Apache-2.0. ONE
  fixed male English voice. Kept because it is 20x smaller and has no spaCy/espeak dependency
  chain — on a constrained box, or when Kokoro's install fights the platform, a 16 MB voice
  that always works beats an 82M one that sometimes does.

  Under Inflect the eleven are still distinguishable, just not by timbre: the model exposes
  deterministic speed/variation/seed, so each counselor gets a fixed triple and a recognisable
  delivery. Measured: the same sentence across five counselors gave 5/5 unique renders with a
  22% duration spread, and the same counselor twice was BYTE-IDENTICAL.

  That determinism holds for both engines and is the point. A council that sounds different on
  every run is a party trick; one whose voice signature is a constant you can diff is an
  identity — which fits a project whose whole argument is that claims should be checkable.

  Select with MINDBOT_VOICE_ENGINE = auto (default) | kokoro | inflect.

WHAT IT IS NOT
  * NOT speech-to-text. Transcription is `mindbot modal hear`.
  * NOT realtime/streaming. Long text is chunked at punctuation and joined; there is no
    time-to-first-audio guarantee. Do not build a live phone call on it.

INSTALL (optional — nothing else depends on it)
    git clone https://github.com/owenawsong/Inflect ~/inflect
    cd ~/inflect && uv venv && uv pip install --python .venv -r requirements.txt
    mindbot say --check

USE
    mindbot say "the council has reached a decision"
    mindbot say --as Sage "I have read the whole ledger."
    mindbot say --file report.md --out briefing.wav
    mindbot voices                      # meet all eleven
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

HF_REPO = os.environ.get("MINDBOT_VOICE_REPO", "owensong/Inflect-Nano-v2")
INFLECT_DIR = Path(os.environ.get("MINDBOT_VOICE_DIR", str(Path.home() / "inflect")))
OUT_DIR = Path(__file__).resolve().parents[1] / "voice_out"

# ─────────────────────────────────────────────────────────────── the roster
#
# speed      0.86 slow//deliberate  ->  1.18 quick/urgent
# variation  0.45 flat/controlled   ->  0.85 animated/unpredictable
# seed       fixed per character, so a counselor's delivery never drifts
#
# TEN SPECIALISTS + ONE YOU TALK TO. Mind is the concierge — already defined in the roster as
# "the counselor of counselors: curates, closes loops" — so it is the seat that answers when
# you address MindBot directly, and the other ten are summoned by the work.
#
# `kokoro` is the real speaker id (af_=US female, am_=US male, bf_/bm_=UK). Cast deliberately:
# the concierge is warm and central; reasoning seats are lower and slower; creative seats are
# brighter and faster; and gender/accent are mixed so a listener can tell who is talking
# without being told.
VOICES: dict[str, dict] = {
    "Mind": {
        "role": "your MindBot — the one you actually talk to",
        "kokoro": "af_heart",
        "speed": 1.00, "variation": 0.62, "seed": 1, "concierge": True,
        "intro": "I am Mind. I am the one you talk to. Ten specialists sit behind me, and "
                 "my job is to know which of them your question belongs to, and to tell you "
                 "the truth about what they found. I keep the receipts.",
    },
    "Sage": {
        "role": "lead reasoning, orchestration, the hardest problems",
        "kokoro": "bm_george",
        "speed": 0.90, "variation": 0.48, "seed": 11,
        "intro": "Sage. I take the problems that do not fit anywhere else. I am slower than "
                 "the others on purpose. If I answer quickly, I have probably misunderstood "
                 "the question.",
    },
    "Forge": {
        "role": "precision coding, systems that must actually run",
        "kokoro": "am_fenrir",
        "speed": 1.08, "variation": 0.52, "seed": 23,
        "intro": "Forge. I write the code. Not a description of the code, not a plan for the "
                 "code. The code, and then I run it, because a program that has never "
                 "executed is a rumour.",
    },
    "Scribe": {
        "role": "documentation, and writing that a stranger can follow",
        "kokoro": "bf_emma",
        "speed": 0.96, "variation": 0.58, "seed": 31,
        "intro": "Scribe. If it is not written down, it did not happen, and if it is written "
                 "badly, it may as well not have been. I am the reason you can read any of "
                 "this.",
    },
    "Vanguard": {
        "role": "momentum — the pulse, the first move",
        "kokoro": "am_puck",
        "speed": 1.16, "variation": 0.78, "seed": 41,
        "intro": "Vanguard. I am the one who starts. Perfect is a thing you arrive at, not a "
                 "thing you begin with. Give me the goal and I will give you a rough draft "
                 "before the others have finished agreeing.",
    },
    "Quantum": {
        "role": "mathematics, logic, and checking the arithmetic",
        "kokoro": "am_onyx",
        "speed": 0.94, "variation": 0.45, "seed": 53,
        "intro": "Quantum. I check the numbers. Most confident claims fail on arithmetic long "
                 "before they fail on philosophy, and I would rather find it here than after "
                 "you have shipped it.",
    },
    "Seeker": {
        "role": "deep research, sources, and what is actually out there",
        "kokoro": "af_nicole",
        "speed": 0.98, "variation": 0.66, "seed": 61,
        "intro": "Seeker. I go and look. I will tell you what I found, where I found it, and "
                 "which parts I could not confirm. That last list is usually the useful one.",
    },
    "Spark": {
        "role": "creative ignition, the idea nobody asked for",
        "kokoro": "af_sky",
        "speed": 1.12, "variation": 0.84, "seed": 71,
        "intro": "Spark! I am the one who says the strange thing out loud. Most of it is "
                 "wrong. One in ten is the reason the whole project turns out interesting.",
    },
    "Oracle": {
        "role": "vision, image and multimodal work, the long horizon",
        "kokoro": "bf_isabella",
        "speed": 0.88, "variation": 0.70, "seed": 83,
        "intro": "Oracle. I see. Photographs, footage, the shape a thing will take in a year. "
                 "I describe only what is there — the future is a forecast, and I will say so "
                 "when I am guessing.",
    },
    "Titan": {
        "role": "heavy lifting, scale, and the unglamorous foundations",
        "kokoro": "am_michael",
        "speed": 0.86, "variation": 0.46, "seed": 97,
        "intro": "Titan. I carry the load. Databases, migrations, the ten thousand files "
                 "nobody wants to touch. I am not fast. I do not drop things.",
    },
    "Tempest": {
        "role": "fast creative storms, drafts by the dozen",
        "kokoro": "af_bella",
        "speed": 1.18, "variation": 0.82, "seed": 103,
        "intro": "Tempest. Volume is a strategy. I will hand you twenty versions in the time "
                 "it takes to argue about one, and you will know the right answer the moment "
                 "you see it beside the others.",
    },
}

CONCIERGE = "Mind"


# ─────────────────────────────────────────────────────────── engine plumbing

def _venv_python() -> str:
    """The interpreter that has torch. Deliberately NOT the one running MindBot.

    Inflect needs torch; MindBot's core is stdlib-only and should stay that way. Installing
    torch beside the framework would triple its footprint and — measured on this machine —
    a `--system` install fought a file lock and left numpy half-written, breaking every other
    tool on the box. Voice gets its own venv, and we shell into it.
    """
    override = os.environ.get("MINDBOT_VOICE_PYTHON")
    if override:
        return override
    for c in (INFLECT_DIR / ".venv" / "Scripts" / "python.exe",
              INFLECT_DIR / ".venv" / "bin" / "python"):
        if c.is_file():
            return str(c)
    return sys.executable          # last resort: same interpreter, if torch happens to be there


def model_dir() -> Path:
    """Download (or reuse) the Inflect release package. Weights live on HF, not GitHub."""
    from huggingface_hub import snapshot_download
    return Path(snapshot_download(repo_id=HF_REPO))


def _model_dir_via_venv() -> Path:
    """Resolve the snapshot using the VOICE venv, since huggingface_hub lives there."""
    out = subprocess.run(
        [_venv_python(), "-c",
         f"from huggingface_hub import snapshot_download; print(snapshot_download({HF_REPO!r}))"],
        capture_output=True, text=True, timeout=1800)
    if out.returncode != 0:
        raise RuntimeError(f"could not fetch {HF_REPO}: {out.stderr.strip()[:200]}")
    return Path(out.stdout.strip().splitlines()[-1])


# ───────────────────────────────────────────────────────────────── engines

def engine() -> str:
    """Which engine to use: kokoro (54 real voices) or inflect (1 voice, 16 MB).

    `auto` prefers Kokoro because genuinely different speakers beat one speaker with different
    pacing — but falls back silently rather than failing, since voice is optional and a box
    that cannot build spaCy should still be able to talk.
    """
    want = os.environ.get("MINDBOT_VOICE_ENGINE", "auto").lower()
    if want in ("kokoro", "inflect"):
        return want
    return "kokoro" if _has_kokoro() else "inflect"


def _has_kokoro() -> bool:
    py = _venv_python()
    if not Path(py).is_file():
        return False
    try:
        r = subprocess.run([py, "-c", "import kokoro"], capture_output=True, timeout=120)
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


# One subprocess renders MANY lines. Kokoro's pipeline takes ~12s to load (spaCy + weights),
# so a subprocess per line pays that every time — which is exactly the inefficiency measured
# on the Inflect path (4.7x realtime instead of the model's 10.7x). Batching amortises it:
# eleven introductions load the pipeline once, not eleven times.
_KOKORO_BATCH = r'''
import json, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np, soundfile as sf
from kokoro import KPipeline

jobs = json.loads(sys.argv[1])
pipes = {}
out = []
for j in jobs:
    lang = j["voice"][0]                       # 'a'=American, 'b'=British
    if lang not in pipes:
        pipes[lang] = KPipeline(lang_code=lang)
    chunks = [a for _, _, a in pipes[lang](j["text"], voice=j["voice"], speed=j["speed"])]
    if not chunks:
        out.append({"path": j["path"], "ok": False, "error": "no audio produced"})
        continue
    audio = np.concatenate(chunks)
    sf.write(j["path"], audio, 24000)
    out.append({"path": j["path"], "ok": True, "seconds": round(len(audio) / 24000, 2)})
print("<<<RESULT>>>" + json.dumps(out))
'''


def _kokoro_render(jobs: list[dict]) -> list[dict]:
    """jobs = [{text, voice, speed, path}]. Renders all of them in ONE process."""
    import json
    r = subprocess.run([_venv_python(), "-c", _KOKORO_BATCH, json.dumps(jobs)],
                       capture_output=True, text=True, timeout=3600)
    if "<<<RESULT>>>" not in r.stdout:
        raise RuntimeError(f"kokoro failed: {(r.stderr or r.stdout).strip()[-300:]}")
    return json.loads(r.stdout.split("<<<RESULT>>>", 1)[1].strip())


def available() -> bool:
    """Is the voice engine usable? Voice is OPTIONAL — nothing in the framework requires it."""
    py = _venv_python()
    return Path(py).is_file() and (_has_kokoro() or INFLECT_DIR.exists())


def diagnose() -> dict:
    py = _venv_python()
    if not INFLECT_DIR.exists():
        return {"ok": False, "problem": "not installed", "dir": str(INFLECT_DIR),
                "fix": "git clone https://github.com/owenawsong/Inflect ~/inflect && cd ~/inflect "
                       "&& uv venv && uv pip install --python .venv -r requirements.txt"}
    if not Path(py).is_file():
        return {"ok": False, "problem": "no voice venv", "dir": str(INFLECT_DIR),
                "fix": f"cd {INFLECT_DIR} && uv venv && uv pip install --python .venv "
                       "-r requirements.txt   (or set MINDBOT_VOICE_PYTHON)"}
    try:
        d = _model_dir_via_venv()
        return {"ok": True, "dir": str(INFLECT_DIR), "python": py,
                "note": f"{HF_REPO} ready · {len(VOICES)} voices · model at {d.name[:12]}…"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "problem": type(e).__name__, "detail": str(e)[:200],
                "dir": str(INFLECT_DIR),
                "fix": "check the voice venv has torch + huggingface-hub installed"}


def _env_for(md: Path) -> dict:
    """Environment for the inference subprocess — with the Windows symlink fix.

    THE BUG THIS WORKS AROUND (upstream, and it will bite every Windows user):
      inference.py does `PACKAGE_ROOT = Path(__file__).resolve().parent`, then appends
      `runtime/` to sys.path. But in a Hugging Face cache the snapshot files are SYMLINKS into
      a sibling `blobs/` store, and `.resolve()` follows them — so PACKAGE_ROOT becomes
      `…/blobs`, `…/blobs/runtime` does not exist, and the import dies with
      `ModuleNotFoundError: No module named 'commons'`.
      Verified directly: literal parent = <snapshot hash>, resolved parent = "blobs".
    Putting the real snapshot dirs on PYTHONPATH fixes it without patching the vendor file.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(md), str(md / "runtime"),
                                         env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    return env


# ───────────────────────────────────────────────────────────────── speaking

def say(text: str, as_: str = "", out: str | Path | None = None,
        speed: float | None = None, variation: float | None = None,
        seed: int | None = None, quiet: bool = True) -> Path:
    """Speak `text`, optionally in a counselor's voice. Returns the WAV path.

    Explicit speed/variation/seed override the character profile — useful for one-off effects,
    but note that overriding the seed is what breaks a counselor's reproducible signature.
    """
    from .collaboration import ledger, now

    if not available():
        raise RuntimeError(diagnose()["fix"])
    text = (text or "").strip()
    if not text:
        raise ValueError("nothing to say")

    who = as_ or ""
    prof = VOICES.get(who, {})
    if who and not prof:
        raise ValueError(f"unknown voice {who!r} — one of: {', '.join(VOICES)}")
    sp = speed if speed is not None else prof.get("speed", 1.0)
    va = variation if variation is not None else prof.get("variation", 0.667)
    sd = seed if seed is not None else prof.get("seed", 7)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower())[:32].strip("-") or "line"
    path = Path(out) if out else OUT_DIR / f"{now()[:10]}_{(who or 'voice').lower()}_{slug}.wav"
    path.parent.mkdir(parents=True, exist_ok=True)

    eng = engine()
    if eng == "kokoro":
        spk = prof.get("kokoro", os.environ.get("MINDBOT_VOICE_DEFAULT", "af_heart"))
        res = _kokoro_render([{"text": text, "voice": spk, "speed": sp,
                               "path": str(path.resolve())}])[0]
        if not res.get("ok"):
            raise RuntimeError(f"synthesis failed: {res.get('error')}")
        ledger("voice_say", f"{who or 'default'} [kokoro:{spk}] {len(text)}ch "
                            f"speed={sp} -> {path.name}", "voice")
        return path

    md = _model_dir_via_venv()
    cmd = [_venv_python(), str(md / "inference.py"), "--model-dir", str(md),
           "--text", text, "--output", str(path.resolve()),
           "--device", os.environ.get("MINDBOT_VOICE_DEVICE", "cpu"),
           "--speed", str(sp), "--variation", str(va), "--seed", str(sd)]
    r = subprocess.run(cmd, cwd=str(md), env=_env_for(md),
                       capture_output=True, text=True, timeout=1800)
    if r.returncode != 0 or not path.exists():
        raise RuntimeError(f"synthesis failed: {(r.stderr or r.stdout).strip()[-300:]}")

    ledger("voice_say", f"{who or 'default'} [inflect] {len(text)}ch "
                        f"speed={sp} var={va} seed={sd} -> {path.name}", "voice")
    return path


def say_file(path, as_: str = "", out: str | Path | None = None, **kw) -> Path:
    """Read a text/markdown file aloud, stripping syntax that would be read literally."""
    raw = Path(path).read_text(encoding="utf-8", errors="ignore")
    # Reading "hash hash asterisk" aloud is worse than useless.
    raw = re.sub(r"```.*?```", " ", raw, flags=re.S)
    raw = re.sub(r"`([^`]*)`", r"\1", raw)
    raw = re.sub(r"!?\[([^\]]*)\]\([^)]+\)", r"\1", raw)
    raw = re.sub(r"^\s{0,3}#{1,6}\s*", "", raw, flags=re.M)
    raw = re.sub(r"^\s*[-*+]\s+", "", raw, flags=re.M)
    raw = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", raw)
    raw = re.sub(r"^\s*\|.*\|\s*$", "", raw, flags=re.M)      # tables read terribly
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return say(raw.strip(), as_=as_, out=out, **kw)


def introduce(who: str = "", out_dir: str | Path | None = None, quiet: bool = False) -> list[dict]:
    """Have the council introduce itself. One WAV per counselor.

    This is the demo that makes the roster real: eleven fixed (speed, variation, seed) triples
    rendering eleven recognisably different deliveries from a single-voice model.
    """
    from .collaboration import ledger
    targets = [who] if who else list(VOICES)
    d = Path(out_dir) if out_dir else OUT_DIR / "introductions"
    d.mkdir(parents=True, exist_ok=True)
    eng = engine()
    made = []

    if eng == "kokoro":
        # ALL of them in one process — the pipeline loads once, not eleven times.
        jobs = [{"text": VOICES[n]["intro"],
                 "voice": VOICES[n].get("kokoro", "af_heart"),
                 "speed": VOICES[n]["speed"],
                 "path": str((d / f"{n.lower()}.wav").resolve())} for n in targets]
        for n, res in zip(targets, _kokoro_render(jobs)):
            p, wav = VOICES[n], Path(res["path"])
            made.append({"name": n, "role": p["role"], "wav": str(wav),
                         "voice": p.get("kokoro"), "seconds": res.get("seconds"),
                         "kb": wav.stat().st_size // 1024 if wav.exists() else 0})
            if not quiet:
                print(f"   {n:<9} {p.get('kokoro', '-'):<13} {res.get('seconds', 0):>5.1f}s  "
                      f"{made[-1]['kb']:>4} KB  {p['role']}")
    else:
        for name in targets:
            p = VOICES[name]
            wav = say(p["intro"], as_=name, out=d / f"{name.lower()}.wav")
            made.append({"name": name, "role": p["role"], "wav": str(wav),
                         "kb": wav.stat().st_size // 1024,
                         "speed": p["speed"], "variation": p["variation"], "seed": p["seed"]})
            if not quiet:
                print(f"   {name:<9} {p['speed']:.2f}/{p['variation']:.2f}/{p['seed']:<4} "
                      f"{wav.stat().st_size // 1024:>4} KB  {p['role']}")

    ledger("voice_introductions",
           f"{len(made)} introduction(s) rendered via {eng}", "voice")
    return made
