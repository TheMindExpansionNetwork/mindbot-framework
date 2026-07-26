"""Build the MindBot promo video from generated assets. Pure ffmpeg + Pillow — no npm, no cloud.

PIPELINE (all inputs are already generated; this only assembles):
  assets/*.png        scene stills      (google/gemini-3.1-flash-image, via OpenRouter)
  assets/hero_*.mp4   hero motion shot  (ByteDance Seedance 2.0 Mini, via ComfyUI Cloud)
  voice/*.wav         character voices  (Windows SAPI — 2 voices x rate variation = 4 speakers)
  cast.json           the script        (each character written by a DIFFERENT model)

STAGES
  1. title/tagline cards rendered with Pillow
  2. per-beat video segments: Ken Burns (zoompan) on stills, or the hero clip passed through
  3. burned-in speaker captions per beat
  4. concat segments -> mux the narration track -> final MP4

Extend: add a beat to BEATS (image|video, the voice file, and the caption). Durations are read
from the voice files, so the cut always matches the read — never hand-tune timings.

Run:  python build_promo.py
"""
import json
import subprocess
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS, VOICE, WORK, OUT = ROOT / "assets", ROOT / "voice", ROOT / "work", ROOT / "out"
W, H, FPS = 1280, 720, 30
PAD = 0.45                 # breathing room after each spoken line (seconds)

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


def run(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"FAILED: {' '.join(str(a) for a in args[:6])}…\n{r.stderr[-1500:]}")
    return r


def dur(path) -> float:
    """Duration of any media file, in seconds."""
    r = run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)])
    return float(r.stdout.strip())


# ── the cut: (kind, source, voice line, speaker caption) ──────────────────────
# Order tells the story: dystopia -> the pitch -> the proof -> the tagline.
BEATS = [
    ("img",   "scene_cubicle.png",     "narrator_0.wav",      "NARRATOR"),
    ("img",   "scene_cubicle_alt.png", "theworker_0.wav",     "THE WORKER"),
    ("img",   "scene_billing.png",     "thebillingbot_0.wav", "THE BILLING BOT"),
    ("img",   "scene_billing.png",     "thebillingbot_1.wav", "THE BILLING BOT"),
    ("img",   "scene_auditor.png",     "theauditor_0.wav",    "THE AUDITOR"),
    ("video", "hero_council.mp4",      "narrator_1.wav",      "NARRATOR"),
    ("img",   "scene_council.png",     "theworker_1.wav",     "THE WORKER"),
    ("img",   "scene_proof.png",       "theauditor_1.wav",    "THE AUDITOR"),
    ("card",  "outro.png",             "narrator_2.wav",      "NARRATOR"),
    ("card",  "outro.png",             "tagline.wav",         ""),
]


def make_cards(tagline: str):
    """Render the outro card with Pillow (no external font deps beyond the system's)."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (W, H), (6, 6, 14))
    d = ImageDraw.Draw(img)
    # eclipse motif: teal corona ring + dark moon
    cx, cy, r = W // 2, H // 2 - 40, 96
    for i in range(26, 0, -1):
        a = int(7 * (i / 26))
        d.ellipse([cx - r - i * 2, cy - r - i * 2, cx + r + i * 2, cy + r + i * 2],
                  fill=(6 + a, 20 + a * 3, 24 + a * 3))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(8, 8, 16), outline=(255, 179, 0), width=3)

    def font(sz):
        for name in ("segoeuib.ttf", "arialbd.ttf", "seguisb.ttf", "arial.ttf"):
            try:
                return ImageFont.truetype(name, sz)
            except OSError:
                continue
        return ImageFont.load_default()

    def center(txt, y, f, fill):
        w = d.textbbox((0, 0), txt, font=f)[2]
        d.text(((W - w) // 2, y), txt, font=f, fill=fill)

    center("MINDBOT", cy + r + 40, font(62), (233, 236, 245))
    center("eleven minds. one command. zero credits.", cy + r + 116, font(24), (50, 230, 200))
    # NB: the tagline is NOT baked in here — it is burned on as a caption by the beat that
    # speaks it (see BEATS). Drawing it in both places double-prints it.
    WORK.mkdir(exist_ok=True)
    img.save(WORK / "outro.png")


def esc(t: str) -> str:
    """Escape a caption for ffmpeg's drawtext filter."""
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def build():
    WORK.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    cast = json.loads((ROOT / "cast.json").read_text(encoding="utf-8"))
    tagline = (ROOT / "tagline.txt").read_text(encoding="utf-8").strip()
    make_cards(tagline)

    # caption text per beat = the spoken line, from the voice manifest
    vman = {m["file"].replace("voice\\", "").replace("voice/", ""): m["text"]
            for m in json.loads((VOICE / "manifest.json").read_text(encoding="utf-8-sig"))}

    segs, tl = [], 0.0
    for i, (kind, src, wav, who) in enumerate(BEATS):
        d = dur(VOICE / wav) + PAD
        seg = WORK / f"seg{i:02d}.mp4"
        line = vman.get(wav, "")
        # wrap the caption to ~52 chars so it fits the frame
        words, rows, cur = line.split(), [], ""
        for w in words:
            if len(cur) + len(w) + 1 > 52:
                rows.append(cur); cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            rows.append(cur)
        rows = rows[:3]

        cap = []
        if who:
            cap.append(f"drawtext=text='{esc(who)}':fontcolor=#32e6c8:fontsize=26:"
                       f"x=(w-text_w)/2:y=h-170:box=1:boxcolor=#06060e@0.55:boxborderw=14")
        for j, row in enumerate(rows):
            cap.append(f"drawtext=text='{esc(row)}':fontcolor=white:fontsize=30:"
                       f"x=(w-text_w)/2:y=h-{124 - j * 38}:box=1:boxcolor=#06060e@0.62:boxborderw=12")
        capf = "," + ",".join(cap) if cap else ""

        if kind == "video":
            vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                  f"fps={FPS},eq=saturation=1.06{capf}")
            run([FFMPEG, "-y", "-stream_loop", "-1", "-i", str(ASSETS / src), "-t", f"{d:.3f}",
                 "-vf", vf, "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                 "-pix_fmt", "yuv420p", str(seg)])
        else:
            path = (WORK if kind == "card" else ASSETS) / src
            frames = max(2, int(d * FPS))
            # Ken Burns: slow push-in on stills; the card holds steady.
            if kind == "card":
                zp = f"scale={W*2}:-2,zoompan=z=1.0:d={frames}:s={W}x{H}:fps={FPS}"
            else:
                zp = (f"scale={W*2}:-2,zoompan=z='min(zoom+0.0009,1.20)':d={frames}:"
                      f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}")
            run([FFMPEG, "-y", "-loop", "1", "-i", str(path), "-t", f"{d:.3f}",
                 "-vf", f"{zp},eq=saturation=1.05{capf}", "-c:v", "libx264",
                 "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", str(seg)])
        segs.append((seg, tl, VOICE / wav))
        tl += d
        print(f"  seg{i:02d} {kind:<5} {src:<22} {d:5.2f}s  {who}")

    # video: concat the segments
    lst = WORK / "segs.txt"
    lst.write_text("".join(f"file '{s.as_posix()}'\n" for s, _, _ in segs), encoding="utf-8")
    silent = WORK / "video.mp4"
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)])

    # audio: lay each voice line at its beat's start offset
    ins, filt = [], []
    for i, (_, start, wav) in enumerate(segs):
        ins += ["-i", str(wav)]
        filt.append(f"[{i}:a]adelay={int(start*1000)}|{int(start*1000)},volume=1.9[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(segs)))
    filt.append(f"{mix}amix=inputs={len(segs)}:dropout_transition=0:normalize=0[out]")
    voice_mix = WORK / "voice_mix.m4a"
    run([FFMPEG, "-y", *ins, "-filter_complex", ";".join(filt), "-map", "[out]",
         "-c:a", "aac", "-b:a", "192k", str(voice_mix)])

    final = OUT / "mindbot_promo.mp4"
    run([FFMPEG, "-y", "-i", str(silent), "-i", str(voice_mix),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)])
    print(f"\n  DONE -> {final}  ({dur(final):.1f}s, {final.stat().st_size//1024} KB)")
    return final


if __name__ == "__main__":
    build()
