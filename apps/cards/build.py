"""AGENT CARDS — an emblem, a full stat card, and a group portrait for the council.

WHAT IT MAKES
    out/emblems/<name>.png   a generated sigil per counselor
    out/cards/<name>.png     a full card: emblem + role + voice + pet + signature
    out/council.png          the whole roster on one sheet
    out/logo.png             the project mark

WHY THE CARD IS COMPOSITED LOCALLY AND NOT GENERATED
  Image models cannot render reliable text. Asking one for "a card with the name Quantum and
  the voice id am_onyx" reliably produces confident gibberish — QUANTVM, an_0nyx — and a card
  whose facts are wrong is worse than no card. So the MODEL draws the emblem, and Pillow lays
  the text over it. Every string on a finished card is read from the framework's own tables
  (VOICES, PETS), so a card cannot disagree with the code it describes.

MODELS
  Tries `openai/gpt-image-2` first, then falls through imagery.FALLBACKS. As of this writing
  gpt-image-2 returns HTTP 400 "Billing hard limit has been reached" from OpenAI upstream — a
  provider-side limit, nothing to do with your key — and the chain silently lands on
  microsoft/mai-image-2.5-pro. That fallback list is the reason a 13-image batch does not die
  on image two.

RUN
    python apps/cards/build.py            # everything, skipping what already exists
    python apps/cards/build.py --force    # regenerate emblems (costs money)
    python apps/cards/build.py --only Sage
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "framework"))

OUT = Path(__file__).resolve().parent / "out"
W, H = 1000, 1400                      # card: 5:7, prints well and reads on a phone

BG, BG2 = (11, 11, 20), (18, 16, 42)
INK, MUTED = (242, 238, 255), (143, 136, 196)
ACCENT, GREEN = (110, 91, 255), (50, 230, 160)

# What each counselor's sigil should look like. Written as OBJECT + MATERIAL + ONE VERB, which
# is what these models actually hold on to; adjective piles get averaged into mush.
SIGILS = {
    "Mind":     "a many-eyed owl mask carved from moonstone, wings folded into a keyhole shape",
    "Sage":     "an ancient tortoise shell inscribed with a spiral of tiny constellations",
    "Forge":    "a glowing anvil struck mid-blow, sparks frozen into geometric circuitry",
    "Scribe":   "a magpie quill writing a line of light that becomes a ribbon of text",
    "Vanguard": "a hare mid-leap dissolving into forward-motion streaks, banner trailing",
    "Quantum":  "a spider suspended in a web of perfect hexagons and numerals",
    "Seeker":   "a hound's head made of brass compass rings, nose pointed to a far star",
    "Prism":    "a fox curled around a shard of split light",
    "Spark":    "a fox leaping through a burst of embers that scatter into small ideas",
    "Oracle":   "a cat's eye reflecting an eclipse, iris made of layered lenses",
    "Titan":    "an ox of dark stone shouldering a stack of stone tablets",
    "Tempest":  "a flock of starlings turning as one into the shape of a single bird",
}

STYLE = ("flat vector emblem, centered on a very dark navy-black field, limited palette of "
         "violet #6E5BFF, mint green #32E6A0 and bone white, thick clean linework, subtle "
         "inner glow, heraldic sigil, symmetrical, NO TEXT, NO LETTERS, NO WORDS")


def font(size, bold=False):
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


def gradient(w, h):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)],
               fill=tuple(int(BG[i] + (BG2[i] - BG[i]) * (1 - abs(t - 0.4) * 1.7)) for i in range(3)))
    return img, d


def rule(d, x, y, w, h=4):
    for i in range(w):
        t = i / max(1, w)
        d.rectangle((x + i, y, x + i + 1, y + h),
                    fill=tuple(int(ACCENT[c] + (GREEN[c] - ACCENT[c]) * t) for c in range(3)))


def emblem(name: str, path: Path, key: str, force=False) -> dict:
    """Generate one sigil. Skips existing files unless --force, because images cost money."""
    from mindbot_pipeline import imagery
    if path.exists() and not force:
        return {"ok": True, "model": "cached", "path": str(path)}
    prompt = f"{SIGILS.get(name, 'an abstract heraldic sigil')}. {STYLE}"
    return imagery.generate(prompt, path, key, aspect="1:1")


def card(name: str, emblem_path: Path, out: Path):
    """Compose the finished card. Every fact comes from the framework's own tables."""
    from PIL import Image
    from mindbot_pipeline import pets as petmod
    from mindbot_pipeline import voice as voicemod

    v = voicemod.VOICES[name]
    p = petmod.PETS[name]
    st = petmod.stats(name)

    img, d = gradient(W, H)

    # emblem, circular-masked so a square generation still sits inside the layout
    if emblem_path.exists():
        from PIL import ImageDraw
        em = Image.open(emblem_path).convert("RGB").resize((620, 620), Image.LANCZOS)
        mask = Image.new("L", (620, 620), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 619, 619), fill=255)
        img.paste(em, (190, 120), mask)
        d.ellipse((190, 120, 810, 740), outline=(70, 58, 130), width=3)

    d.text((70, 790), name.upper(), font=font(96, True), fill=INK)
    rule(d, 74, 905, 520, 5)

    # role, wrapped by hand — textwrap mis-measures proportional fonts at this size
    words, line, lines = v["role"].split(), "", []
    for w_ in words:
        if len(line) + len(w_) > 40:
            lines.append(line.strip()); line = ""
        line += w_ + " "
    lines.append(line.strip())
    y = 945
    for ln in lines[:3]:
        d.text((74, y), ln, font=font(38), fill=(214, 208, 250))
        y += 50

    y = max(y + 30, 1090)
    rows = [
        ("VOICE", v.get("kokoro", "—"), GREEN),
        # No emoji glyph here. Pillow renders it from a monochrome system font, which has no
        # emoji coverage, so 🐢 comes out as a tofu box — worse than simply omitting it. The
        # glyph belongs in the terminal (`mindbot pets`), where the shell has a colour font.
        ("PET", f"{p['name']} the {p['species']}", INK),
        ("RUNS", p["runs"][:46], MUTED),
        ("TIER", f"{st['tier']} · {st['actions']} errands", GREEN if st["actions"] > 25 else MUTED),
    ]
    for label, val, col in rows:
        d.text((74, y), label, font=font(22, True), fill=(96, 88, 150))
        d.text((240, y - 4), str(val), font=font(30), fill=col)
        y += 54

    d.text((74, H - 90), "MINDBOT", font=font(26, True), fill=(80, 72, 130))
    d.text((74, H - 56), "prove, don't promise", font=font(24), fill=(70, 62, 118))
    d.text((W - 250, H - 90), f"speed {v['speed']:.2f}", font=font(24), fill=(80, 72, 130))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)


def council_sheet(names, emblems: Path, out: Path):
    """All eleven on one sheet — the shareable artifact."""
    from PIL import Image, ImageDraw
    cols, cw, ch = 4, 480, 560
    w, h = cols * cw + 80, ((len(names) + cols - 1) // cols) * ch + 300
    img, d = gradient(w, h)

    d.text((60, 70), "THE COUNCIL", font=font(110, True), fill=INK)
    rule(d, 66, 210, 700, 6)
    d.text((66, 250), "eleven lenses · one ledger · nothing sent without you",
           font=font(38), fill=MUTED)

    from mindbot_pipeline import voice as voicemod
    for i, n in enumerate(names):
        x, y = 40 + (i % cols) * cw, 340 + (i // cols) * ch
        ep = emblems / f"{n.lower()}.png"
        if ep.exists():
            em = Image.open(ep).convert("RGB").resize((380, 380), Image.LANCZOS)
            mask = Image.new("L", (380, 380), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 379, 379), fill=255)
            img.paste(em, (x + 45, y), mask)
            d.ellipse((x + 45, y, x + 425, y + 380), outline=(64, 54, 120), width=2)
        d.text((x + 48, y + 400), n.upper(), font=font(44, True), fill=INK)
        d.text((x + 48, y + 456), voicemod.VOICES[n].get("kokoro", ""), font=font(26), fill=GREEN)
    img.save(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="regenerate emblems (costs money)")
    ap.add_argument("--only", default="", help="one counselor")
    args = ap.parse_args()

    from mindbot_pipeline import models  # noqa: F401 — loads .env
    from mindbot_pipeline import voice as voicemod
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("  no OPENROUTER_API_KEY"); return 1

    names = [args.only] if args.only else list(voicemod.VOICES)
    emb, crd = OUT / "emblems", OUT / "cards"
    emb.mkdir(parents=True, exist_ok=True)
    crd.mkdir(parents=True, exist_ok=True)

    print(f"\n  {len(names)} counselor(s)\n")
    made = 0
    for n in names:
        t = time.time()
        r = emblem(n, emb / f"{n.lower()}.png", key, force=args.force)
        if not r["ok"]:
            print(f"   {n:<10} FAILED — {r.get('attempts')}")
            continue
        card(n, emb / f"{n.lower()}.png", crd / f"{n.lower()}.png")
        made += 1
        print(f"   {n:<10} {r['model'][:34]:<34} {time.time()-t:>5.1f}s")

    if not args.only:
        council_sheet(names, emb, OUT / "council.png")
        print(f"\n   council sheet -> {OUT / 'council.png'}")
    print(f"\n   {made}/{len(names)} cards -> {crd}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
