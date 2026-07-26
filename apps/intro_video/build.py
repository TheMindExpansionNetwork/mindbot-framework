"""INTRO VIDEO — the council introduces itself, as something you can watch.

WHY THIS EXISTS
  Audio files are a bad deliverable. They do not preview in most chat clients, they do not
  autoplay on social, and a folder of eleven .wav files is not a thing anyone listens to. A
  single MP4 with the speaker's name on screen is watchable everywhere and shareable in one
  link.

WHAT IT MAKES
  A title card, eleven counselor cards timed to their own narration, and a closing card —
  concatenated into one MP4. Every card is drawn here with Pillow; there are no external
  assets, no fonts to install, and no network calls, so this runs identically on a laptop and
  on a headless VPS.

RUN
    python apps/intro_video/build.py                 # uses existing introductions
    python apps/intro_video/build.py --render        # re-render the audio first

REQUIRES
    ffmpeg on PATH · Pillow · a voice engine (mindbot say --check)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "framework"))

W, H = 1920, 1080
FPS = 30
OUT = ROOT / "apps" / "intro_video" / "out"

# Brand palette — same values as assets/banner.svg, so the video and the README agree.
BG = (11, 11, 20)
BG2 = (18, 16, 42)
INK = (242, 238, 255)
MUTED = (143, 136, 196)
ACCENT = (110, 91, 255)
GREEN = (50, 230, 160)


def _font(size: int, bold: bool = False):
    """Best available system font. Falls back to Pillow's bitmap default.

    Deliberately tries a list rather than shipping a .ttf: bundling a font means bundling its
    licence, and this file is meant to be copy-pasteable.
    """
    from PIL import ImageFont
    names = (["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold
             else ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"])
    for n in names:
        for base in ("C:/Windows/Fonts/", "/usr/share/fonts/truetype/dejavu/", ""):
            try:
                return ImageFont.truetype(base + n, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _canvas():
    """Dark vertical gradient + the eclipse motif, drawn once per card."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for y in range(H):                       # cheap vertical gradient
        t = y / H
        d.line([(0, y), (W, y)],
               fill=tuple(int(BG[i] + (BG2[i] - BG[i]) * (1 - abs(t - 0.45) * 1.6)) for i in range(3)))
    # the eclipse: a lit disc with a dark body sliding across it
    cx, cy, r = W - 300, 300, 150
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=INK)
    d.ellipse((cx - r - 34, cy - r - 30, cx + r - 34, cy + r - 30), fill=BG)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(60, 50, 120), width=2)
    return img, d


def _rule(d, x, y, w, h=4):
    """A purple→green gradient rule. The one recurring graphic element."""
    for i in range(w):
        t = i / max(1, w)
        d.rectangle((x + i, y, x + i + 1, y + h),
                    fill=tuple(int(ACCENT[c] + (GREEN[c] - ACCENT[c]) * t) for c in range(3)))


def title_card(path: Path):
    img, d = _canvas()
    d.text((140, 330), "MINDBOT", font=_font(150, True), fill=INK)
    _rule(d, 146, 510, 760, 5)
    d.text((146, 560), "The agent you can prove.", font=_font(58), fill=(220, 214, 255))
    d.text((146, 660), "Eleven counselors. One ledger. Nothing sent without you.",
           font=_font(34), fill=MUTED)
    d.text((146, 900), "prove, don't promise", font=_font(30), fill=GREEN)
    img.save(path)


def counselor_card(path: Path, name: str, role: str, voice: str, idx: int, total: int):
    img, d = _canvas()
    d.text((140, 250), f"{idx:02d} / {total:02d}", font=_font(30), fill=(80, 72, 130))
    d.text((140, 310), name.upper(), font=_font(130, True), fill=INK)
    _rule(d, 146, 470, 620, 5)
    # Role wraps by hand — textwrap on a proportional font mis-measures badly at this size.
    words, line, lines = role.split(), "", []
    for w_ in words:
        if len(line) + len(w_) > 46:
            lines.append(line.strip())
            line = ""
        line += w_ + " "
    lines.append(line.strip())
    y = 530
    for ln in lines[:3]:
        d.text((146, y), ln, font=_font(46), fill=(214, 208, 250))
        y += 62
    d.text((146, 880), f"voice · {voice}", font=_font(30), fill=GREEN)
    d.text((146, 930), "every word it says is written to the ledger", font=_font(26), fill=MUTED)
    img.save(path)


def outro_card(path: Path, stats: dict):
    img, d = _canvas()
    d.text((140, 250), "RUN IT YOURSELF", font=_font(92, True), fill=INK)
    _rule(d, 146, 380, 700, 5)
    d.text((146, 440), "curl -fsSL mindbot.sh | bash", font=_font(40), fill=(214, 208, 250))
    y = 560
    for k, v in stats.items():
        d.text((146, y), v, font=_font(38), fill=GREEN)
        d.text((320, y), k, font=_font(38), fill=MUTED)
        y += 60
    d.text((146, 930), "github.com/TheMindExpansionNetwork/mindbot-observe",
           font=_font(30), fill=(150, 140, 220))
    img.save(path)


def wav_seconds(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def segment(card: Path, audio: Path, out: Path, pad: float = 0.6):
    """One still card + its narration -> an MP4 segment.

    `pad` adds breathing room after the line so cards do not cut the instant a voice stops,
    which reads as a glitch rather than an edit.
    """
    dur = wav_seconds(audio) + pad
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-framerate", str(FPS), "-i", str(card),
        "-i", str(audio),
        "-filter_complex", f"[1:a]apad=pad_dur={pad}[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-t", f"{dur:.2f}", str(out)],
        check=True, capture_output=True, timeout=600)
    return dur


def silent_segment(card: Path, out: Path, seconds: float):
    """A card with no narration — needs a synthetic silent track or concat drops the audio."""
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-framerate", str(FPS), "-i", str(card),
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-t", str(seconds), str(out)],
        check=True, capture_output=True, timeout=600)
    return seconds


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--render", action="store_true", help="re-render the introductions first")
    ap.add_argument("--out", default=str(OUT / "mindbot_intro.mp4"))
    args = ap.parse_args()

    from mindbot_pipeline import voice
    OUT.mkdir(parents=True, exist_ok=True)
    cards = OUT / "cards"
    cards.mkdir(exist_ok=True)
    segs = OUT / "segments"
    segs.mkdir(exist_ok=True)

    intro_dir = voice.OUT_DIR / "introductions"
    if args.render or not any(intro_dir.glob("*.wav")):
        print("  rendering introductions…")
        voice.introduce(quiet=True)

    names = [n for n in voice.VOICES if (intro_dir / f"{n.lower()}.wav").exists()]
    if not names:
        print("  no introductions found — run: mindbot voices --introduce")
        return 1

    print(f"\n  building {len(names) + 2} segments at {W}x{H}\n")
    parts, total = [], 0.0

    title_card(cards / "00_title.png")
    parts.append(segs / "00.mp4")
    total += silent_segment(cards / "00_title.png", parts[-1], 4.0)
    print(f"   title                              4.0s")

    for i, n in enumerate(names, 1):
        p = voice.VOICES[n]
        c = cards / f"{i:02d}_{n.lower()}.png"
        counselor_card(c, n, p["role"], p.get("kokoro", "inflect"), i, len(names))
        s = segs / f"{i:02d}.mp4"
        d = segment(c, intro_dir / f"{n.lower()}.wav", s)
        parts.append(s)
        total += d
        print(f"   {n:<10} {p.get('kokoro', '-'):<14} {d:>5.1f}s")

    from mindbot_pipeline import identity
    w = identity.whoami()
    outro_card(cards / "99_outro.png", {
        "counselors": f"{len(names)}",
        "recorded actions": f"{w['history']['recorded_actions']:,}",
        "autonomous sends": f"{w['standing'].get('autonomous_external_actions', 0)}",
        "commands": f"{w['capabilities']['command_count']}",
    })
    parts.append(segs / "99.mp4")
    total += silent_segment(cards / "99_outro.png", parts[-1], 6.0)
    print(f"   outro                              6.0s")

    lst = OUT / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    out = Path(args.out)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(out)], check=True, capture_output=True, timeout=1200)

    mb = out.stat().st_size / 1e6
    print(f"\n   {out}")
    print(f"   {total / 60:.1f} min · {mb:.1f} MB · {W}x{H} @ {FPS}fps\n")
    try:
        from mindbot_pipeline.collaboration import ledger
        ledger("intro_video", f"{len(names)} counselors · {total:.0f}s · {mb:.1f}MB", "video")
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
