"""OBSERVE — describe media, and make the description provable.

THE IDEA
  Every AI can look at a photo and tell you what is in it. None of them can prove, afterwards,
  that they said it — or that the file they looked at is the file you are holding now.

  Observe looks at each image and audio file, then writes THREE things into the hash-chained
  ledger for every observation:

      * sha256 of the FILE BYTES     — binds the claim to that exact file
      * sha256 of the OBSERVATION    — binds it to that exact wording
      * the timestamp and seq        — binds it to a position in an append-only chain
                                       whose Merkle root gets published to a third party

  From that you get a claim nobody else in this space can make:

      "This model saw THIS EXACT FILE, at THIS TIME, and said THIS —
       and here is a proof you can check without trusting me or the model vendor."

  Change one pixel and the file hash stops matching. Reword the description and the observation
  hash stops matching. Rewrite history and the published anchors stop matching. Selective
  disclosure works too: `mindbot prove <seq>` proves ONE observation belongs to the catalog
  without revealing the other files at all — which matters when the folder is evidence, medical
  imaging, or anything else where showing everything is not an option.

WHY IT NEEDED A MULTIMODAL ENDPOINT
  Until the Modal endpoint landed, every model in this stack was text-only, so "describe this
  photo" was not something the council could do at all. Observe is the first thing built on
  Inkling's image + audio input, and it runs entirely on an endpoint you host: fixed cost
  against prepaid credits, so cataloguing a thousand files does not touch a metered budget.

USE
    mindbot observe ./photos
    mindbot observe ./photos --json
    mindbot prove 481                  # prove one observation, reveal nothing else
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .collaboration import ROOT, ledger, now

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}

# Big files are slow to base64 and slower to upload; the model card's own guidance is 40-4096px
# images and audio under ~20 minutes. Refuse rather than hang, and say why.
MAX_BYTES = 25 * 1024 * 1024

CATALOG = ROOT / "framework" / "observations"

IMAGE_PROMPT = (
    "Describe this image factually and specifically. Cover: subject, setting, notable text "
    "(quote it exactly), colours, and anything unusual. Do not speculate about intent or "
    "meaning. If text is unreadable, say so rather than guessing."
)
AUDIO_PROMPT = (
    "Transcribe this audio verbatim. Then, on a new line beginning 'NOTES:', describe the "
    "speaker count, tone, and any non-speech sound. If a passage is inaudible, write "
    "[inaudible] rather than guessing at it."
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scan(folder) -> list[Path]:
    """Find observable media, newest first. Skips our own outputs."""
    d = Path(folder)
    if not d.is_dir():
        raise NotADirectoryError(f"{d} is not a folder")
    out = [p for p in sorted(d.rglob("*"))
           if p.is_file() and p.suffix.lower() in (IMAGE_EXT | AUDIO_EXT)
           and "observations" not in p.parts]
    return out


def observe(path: Path) -> dict:
    """Observe ONE file and record the observation in the ledger.

    The ledger entry is written even when the model call fails, because "we tried to look at
    this file at this time and could not" is itself a fact worth being able to prove. A catalog
    with silent holes in it is not a catalog.
    """
    from . import modal_endpoint as me

    raw = path.read_bytes()
    file_hash = _sha(raw)
    kind = "image" if path.suffix.lower() in IMAGE_EXT else "audio"
    rec = {"file": str(path), "name": path.name, "kind": kind,
           "bytes": len(raw), "file_sha256": file_hash, "observed": now()}

    if len(raw) > MAX_BYTES:
        rec.update(ok=False, error=f"{len(raw) / 1e6:.1f} MB exceeds the {MAX_BYTES / 1e6:.0f} MB limit")
        ledger("observe_skip", f"{path.name} sha={file_hash[:16]}… too large", "observer")
        return rec

    try:
        text = (me.describe_image(path, IMAGE_PROMPT) if kind == "image"
                else me.transcribe(path, AUDIO_PROMPT))
        rec.update(ok=True, observation=text.strip(),
                   observation_sha256=_sha(text.strip().encode("utf-8")))
    except Exception as e:  # noqa: BLE001 — a bad file must not abandon the whole catalog
        rec.update(ok=False, error=f"{type(e).__name__}: {str(e)[:160]}")

    # The ledger line carries BOTH hashes, so the entry alone is enough to verify a claim
    # later — you do not need this catalog file to have survived.
    detail = (f"{kind} {path.name} file={file_hash[:16]}… "
              + (f"obs={rec['observation_sha256'][:16]}… {len(rec['observation'])}ch"
                 if rec.get("ok") else f"FAILED {rec.get('error', '')[:60]}"))
    rec["seq"] = _ledger_seq("observe_file", detail)
    return rec


def _ledger_seq(event: str, detail: str) -> int | None:
    """Write a ledger entry and return the seq it landed at, so the catalog can cite it."""
    ledger(event, detail, "observer")
    try:
        from . import collaboration
        head = json.loads((collaboration.COLLAB / "ledger.jsonl.head").read_text(encoding="utf-8"))
        return head.get("seq")
    except Exception:  # noqa: BLE001 — the entry is written either way; only the citation is lost
        return None


def run(folder, quiet: bool = False) -> dict:
    """Catalog a folder. Returns the catalog and writes it next to the media."""
    files = scan(folder)

    def say(m):
        if not quiet:
            print(m)

    if not files:
        say(f"\n  no images or audio found in {folder}\n")
        return {"folder": str(folder), "observations": [], "ok": 0, "failed": 0}

    say(f"\n  ┌─ OBSERVE · {len(files)} file(s) · {Path(folder).resolve().name}")
    obs = []
    for i, p in enumerate(files, 1):
        r = observe(p)
        obs.append(r)
        mark = "✓" if r.get("ok") else "✗"
        note = (r["observation"][:58].replace("\n", " ") if r.get("ok")
                else r.get("error", "")[:58])
        say(f"  ├─ {mark} {i:>2}/{len(files)} {r['kind']:<5} {p.name[:26]:<26} {note}")

    ok = sum(1 for r in obs if r.get("ok"))
    cat = {"folder": str(Path(folder).resolve()), "generated": now(),
           "files": len(files), "ok": ok, "failed": len(files) - ok,
           "model": _model_name(), "observations": obs}

    CATALOG.mkdir(parents=True, exist_ok=True)
    stem = f"{now()[:10]}_{Path(folder).resolve().name}"
    (CATALOG / f"{stem}.json").write_text(json.dumps(cat, indent=2), encoding="utf-8")
    md = CATALOG / f"{stem}.md"
    md.write_text(as_markdown(cat), encoding="utf-8")

    ledger("observe_catalog", f"{Path(folder).resolve().name}: {ok}/{len(files)} observed", "observer")
    say(f"  └─ {ok}/{len(files)} observed → {md.name}")
    if ok:
        seqs = [r["seq"] for r in obs if r.get("seq")]
        if seqs:
            say(f"\n   every observation is in the chain. prove one: "
                f"mindbot prove {seqs[0]}")
    return cat


# ─────────────────────────────────────────────────────────────────── video

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

WATCH_PROMPT = (
    "Review this fixed security camera frame. Reply in EXACTLY this format, nothing before it:\n"
    "NOTABLE: yes|no\n"
    "PEOPLE: <integer>\n"
    "VEHICLES: <integer>\n"
    "DESC: <one line of what is visible>\n\n"
    "NOTABLE is yes ONLY if a person, vehicle, or animal is present, or something has obviously "
    "changed or been disturbed. An empty scene is no, however architecturally interesting. "
    "Report only what is visible; do not speculate about intent."
)

# WHY LINE-ORIENTED OUTPUT AND NOT JSON SCHEMA.
#
# Three designs were measured against this endpoint, in order:
#
#   1. Sentinel phrase ("say NOTHING OF NOTE if quiet") — the model PARAPHRASED it as "No
#      people or vehicles visible", so every empty frame became an alarm. Unusable.
#   2. Strict json_schema — the server advertises it and mostly honours it, but on image
#      inputs it truncated the object mid-write ~50% of the time, returning
#      '{\n\n\n"notable": false' with finish_reason "stop". Raising max_tokens to 12000 and
#      dropping reasoning_effort to "low" both failed to fix it.
#   3. This.
#
# The decisive property is TRUNCATION BEHAVIOUR. Truncated JSON is worth nothing — lose the
# closing brace and the entire payload is unparseable, including the one field you cared
# about. Line-oriented output degrades gracefully: NOTABLE is on line 1, so it survives even
# if the description is cut off. On an unreliable channel, put the critical bit first and make
# it independently parseable.
#
# The regexes are anchored and tolerant of case and spacing, and anything unparseable is
# treated as a FAILED review rather than a quiet frame — see the ok/notable handling below.
_RE_NOTABLE = re.compile(r"^\s*NOTABLE\s*:\s*(yes|no|true|false)", re.I | re.M)
_RE_PEOPLE = re.compile(r"^\s*PEOPLE\s*:\s*(\d+)", re.I | re.M)
_RE_VEHICLES = re.compile(r"^\s*VEHICLES\s*:\s*(\d+)", re.I | re.M)
_RE_DESC = re.compile(r"^\s*DESC\s*:\s*(.+)", re.I | re.M)


def parse_frame_report(text: str) -> dict | None:
    """Parse the line format. Returns None if NOTABLE is missing — that is a failed review.

    NOTABLE is the only field that must be present. Losing the count or the description costs
    detail; losing NOTABLE costs the entire point of the frame, so its absence is an error
    rather than a default.
    """
    m = _RE_NOTABLE.search(text or "")
    if not m:
        return None
    desc = _RE_DESC.search(text or "")
    ppl = _RE_PEOPLE.search(text or "")
    veh = _RE_VEHICLES.search(text or "")
    return {
        "notable": m.group(1).lower() in ("yes", "true"),
        "people": int(ppl.group(1)) if ppl else 0,
        "vehicles": int(veh.group(1)) if veh else 0,
        "description": (desc.group(1).strip() if desc else text.strip()[:400]),
    }

# What a frame costs, so nobody has to guess. An observation is ~1k output tokens plus the
# image's own token cost; at $5/Mtok that is roughly $0.005-0.01 per frame. The arithmetic
# that matters for a camera:
#     1 frame/min  = 1,440/day  ≈ $7-14/day    per camera   <- too much for always-on
#     1 frame/5min =   288/day  ≈ $1.40-2.90/day
#     1 frame/15min=    96/day  ≈ $0.50-1.00/day            <- sane for a quiet site
# On a SELF-HOSTED endpoint all of these are $0 in metered terms — you are paying for GPU
# time you already bought. That is the whole argument for hosting it yourself.
COST_PER_FRAME_USD = 0.0075


def sample_frames(video, every_seconds: int = 60, out_dir=None, limit: int = 0) -> list[Path]:
    """Pull one frame every `every_seconds` using ffmpeg.

    Sampling rather than decoding every frame is the entire point: a 24h camera feed is ~2M
    frames and ~$15,000 to describe. At one frame a minute it is 1,440 frames and a few dollars
    — and for a static scene, a minute of granularity loses almost nothing.
    """
    import subprocess
    v = Path(video)
    if not v.is_file():
        raise FileNotFoundError(v)
    out = Path(out_dir) if out_dir else (CATALOG / "frames" / v.stem)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("frame_*.jpg"):
        old.unlink()
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(v),
           "-vf", f"fps=1/{max(1, every_seconds)}",
           # Scale long edge to 1024: the model card's useful range tops out around there, and
           # a 4K frame costs several times the tokens for no extra detected detail.
           "-vf", f"fps=1/{max(1, every_seconds)},scale='min(1024,iw)':-2",
           "-q:v", "4"]
    if limit:
        cmd += ["-frames:v", str(limit)]
    cmd.append(str(out / "frame_%05d.jpg"))
    subprocess.run(cmd, check=True, capture_output=True, timeout=1800)
    return sorted(out.glob("frame_*.jpg"))


def watch(video, every_seconds: int = 60, limit: int = 0, quiet: bool = False) -> dict:
    """Watch a video one frame per interval and record every observation.

    Built for the case where footage has to hold up later: a security review, an incident,
    an environmental before/after. The value is not that a model watched it — anything can do
    that. It is that each frame's observation is bound to that frame's bytes and to a chain
    position published to a third party, so "the camera saw nothing at 03:14" is checkable
    rather than assertable.
    """
    from . import modal_endpoint as me

    def say(m):
        if not quiet:
            print(m)

    v = Path(video)
    say(f"\n  ┌─ WATCH · {v.name} · 1 frame / {every_seconds}s")
    frames = sample_frames(v, every_seconds, limit=limit)
    if not frames:
        say("  └─ no frames extracted — is this a video file?")
        return {"video": str(v), "frames": 0, "events": [], "quiet_frames": 0}

    est = len(frames) * COST_PER_FRAME_USD
    say(f"  ├─ {len(frames)} frame(s)   {'~$%.2f metered, $0 self-hosted' % est}")

    obs, events = [], []
    for i, f in enumerate(frames, 1):
        stamp = (i - 1) * every_seconds
        raw = f.read_bytes()
        fh = _sha(raw)
        people = vehicles = 0
        try:
            # effort="low": "is a person in this frame" is a classification, not a puzzle, and
            # reasoning tokens are spent before the answer is written.
            raw_reply = me.chat("You are a precise security reviewer.", WATCH_PROMPT,
                                images=[f], max_tokens=1200, effort="low")
            r = parse_frame_report(raw_reply)
            if r is None:
                # Unparseable means UNREVIEWED, not quiet. Defaulting an unreadable answer to
                # "nothing here" is how a monitoring system quietly stops monitoring.
                raise ValueError(f"unparseable frame report: {raw_reply.strip()[:100]!r}")
            ok = True
            notable = r["notable"]
            people, vehicles = r["people"], r["vehicles"]
            text = r["description"]
        except Exception as e:  # noqa: BLE001
            # A FAILED FRAME IS NOT A QUIET FRAME.
            # The first version set notable=False here, so a total outage — every call dying on
            # a transient DNS error — reported as "6 quiet frames", which reads as ALL CLEAR.
            # An error indistinguishable from an all-clear is the single worst failure mode a
            # security log can have, and it is the exact silent-failure class this project
            # exists to argue against. Failures are now counted and surfaced separately, and
            # `notable` is left False only because it is meaningless here — `ok` is what counts.
            text, ok, notable = f"{type(e).__name__}: {str(e)[:120]}", False, False
        # Quiet frames are recorded too. A provable ABSENCE is the whole point of a security
        # log — a gap is indistinguishable from a deletion, which is exactly what anyone
        # tampering would rely on.
        rec = {"frame": f.name, "t_seconds": stamp,
               "timecode": f"{stamp // 3600:02d}:{stamp % 3600 // 60:02d}:{stamp % 60:02d}",
               "file_sha256": fh, "ok": ok, "notable": notable,
               "people": people, "vehicles": vehicles, "observation": text,
               "observation_sha256": _sha(text.encode("utf-8"))}
        rec["seq"] = _ledger_seq("watch_frame",
                                 f"{v.name} t={rec['timecode']} frame={fh[:16]}… "
                                 + (f"NOTABLE p={people} v={vehicles} " if notable else "quiet ")
                                 + text[:60].replace("\n", " "))
        obs.append(rec)
        if not ok:
            say(f"  ├─ ✗ {rec['timecode']}  UNREVIEWED — {text[:52]}")
        elif notable:
            events.append(rec)
            tag = f"p{people}" + (f" v{vehicles}" if vehicles else "")
            say(f"  ├─ ⚑ {rec['timecode']} [{tag}] {text[:56].splitlines()[0]}")
        elif not quiet and i % 10 == 0:
            say(f"  ├─ · {rec['timecode']}  ({i}/{len(frames)} quiet)")

    failed = [r for r in obs if not r["ok"]]
    cat = {"video": str(v.resolve()), "generated": now(), "every_seconds": every_seconds,
           "frames": len(frames), "notable": len(events),
           # `quiet` counts only frames that were ACTUALLY REVIEWED and found empty. Frames that
           # errored are `unreviewed` — a distinct, louder category. Rolling them into "quiet"
           # would let an outage read as an all-clear.
           "quiet_frames": len(frames) - len(events) - len(failed),
           "unreviewed": len(failed),
           "coverage": round(1 - len(failed) / max(1, len(frames)), 3),
           "model": _model_name(), "est_metered_usd": round(est, 3), "observations": obs}
    CATALOG.mkdir(parents=True, exist_ok=True)
    stem = f"{now()[:10]}_watch_{v.stem}"
    (CATALOG / f"{stem}.json").write_text(json.dumps(cat, indent=2), encoding="utf-8")
    ledger("watch_done",
           f"{v.name}: {len(events)} notable, {cat['quiet_frames']} quiet, "
           f"{len(failed)} UNREVIEWED of {len(frames)} frames "
           f"(coverage {cat['coverage']:.0%})", "observer")
    say(f"  └─ {len(events)} notable · {cat['quiet_frames']} quiet · "
        + (f"{len(failed)} UNREVIEWED · " if failed else "")
        + f"{stem}.json")
    if failed:
        # Loud, and it costs the run a non-zero exit at the CLI layer. A gap in a security log
        # that nobody notices is the thing an attacker relies on.
        say(f"\n   ⚠ COVERAGE {cat['coverage']:.0%} — {len(failed)} frame(s) were never reviewed.")
        say(f"     Those minutes are NOT cleared. First failure: {failed[0]['observation'][:70]}")
    if obs:
        say(f"\n   every frame is in the chain, including the quiet ones."
            f"\n   prove one: mindbot prove {obs[0]['seq']}")
    return cat


def _model_name() -> str:
    import os
    from . import modal_endpoint as me
    return os.environ.get("MODAL_MODEL", me.DEFAULT_MODEL)


def as_markdown(cat: dict) -> str:
    lines = [
        f"# Observation catalog — {Path(cat['folder']).name}",
        "",
        f"**{cat['ok']}/{cat['files']} observed** · {cat['generated']} · model `{cat['model']}`",
        "",
        "Every observation below is recorded in a hash-chained, externally anchored ledger.",
        "Each row carries the SHA-256 of the file it describes, so the claim is bound to those",
        "exact bytes — change one pixel and it stops matching.",
        "",
        "```bash",
        "mindbot verify              # the chain is unbroken",
        "mindbot notarize --audit    # today's history still matches every published anchor",
        f"mindbot prove {next((r['seq'] for r in cat['observations'] if r.get('seq')), 1)}"
        "              # prove ONE observation, revealing nothing about the others",
        "```",
        "",
    ]
    for r in cat["observations"]:
        lines += [f"## {r['name']}", ""]
        lines += [f"- **kind** {r['kind']} · {r['bytes'] / 1024:.0f} KB",
                  f"- **file sha256** `{r['file_sha256']}`"]
        if r.get("seq"):
            lines.append(f"- **ledger seq** {r['seq']}")
        if r.get("ok"):
            lines += [f"- **observation sha256** `{r['observation_sha256']}`", "",
                      "> " + r["observation"].replace("\n", "\n> "), ""]
        else:
            lines += ["", f"> **not observed** — {r.get('error', 'unknown')}", ""]
    lines += ["---", "",
              "*Produced by MindBot Observe. The model described these files; the ledger proves",
              "it did so, when, and that nothing has been altered since.*"]
    return "\n".join(lines) + "\n"
