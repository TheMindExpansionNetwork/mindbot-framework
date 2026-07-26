"""NOVA SPACE BURGERS — generate the campaign artwork from the brand bible's own prompts.

The four ad prompts below are VERBATIM from the Firm's brand bible (firm_runs/…_firm.json).
They were not rewritten to make the images come out nicer, because the point of this exercise
is to show the pipeline end to end: the council wrote the creative brief, and the image models
executed it unedited. A prompt improved by hand afterwards would quietly turn a demonstration
into a curation.

Model order comes from imagery.FALLBACKS — gpt-image-2 first, then MAI, then Gemini. Whichever
one answers is recorded per image so the README can say who drew what.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "framework"))

OUT = Path(__file__).resolve().parent / "out"

# Verbatim from the brand bible. Only the trailing style anchor is ours, and it is identical
# across all four so no single ad gets a hand-tuned advantage.
ANCHOR = (" Retro-futurist corporate advertising art, saturated palette, glossy print campaign, "
          "no readable text, no lettering, no watermark.")

ADS = [
    ("orbital-family", "FAMILY DINNER, NOW WITH ORBITAL COVERAGE.",
     "Retro-futurist fast-food billboard, smiling family in matching NOVA SPACE BURGERS "
     "uniforms eating burgers inside a spotless lunar habitat, Earth visible through window, "
     "friendly corporate mascot waving, saturated red, chrome, and electric-blue palette, "
     "1970s space-age advertising illustration, tiny cheerful legal text at bottom."),
    ("lunch-promotion", "YOUR LUNCH BREAK DESERVES A PROMOTION.",
     "Cheerful exhausted office worker floating in zero gravity toward a glowing NOVA SPACE "
     "BURGERS counter, burger presented like a medal by a smiling service robot, corporate "
     "space station cubicles behind them, polished sci-fi commercial, bright optimistic "
     "lighting, subtle dystopian details."),
    ("space-juice", "SPACE JUICE: HYDRATION IS COMPLIANCE.",
     "Luminous neon-blue SPACE JUICE cup glowing on a pristine cafeteria table, diverse workers "
     "smiling with identical expressions, gigantic NOVA logo reflected in the cup, sleek "
     "interplanetary corporate campus, vintage magazine ad composition, fine-print disclaimer "
     "strip."),
    ("best-on-planet", "THE BEST BURGERS ON THE PLANET.*",
     "Heroic double burger floating above a rotating unidentified planet, NOVA SPACE BURGERS "
     "flag planted on its surface, fireworks, smiling astronauts applauding, glossy 1980s "
     "fast-food campaign style, triumphant red-and-gold typography, asterisk prominently "
     "visible."),
]

# The mark, and a portrait sheet for the executive team.
EXTRAS = [
    ("logo", "1:1",
     "A corporate logo mark for a fast-food megacorp: a stylised burger silhouette contained "
     "inside a bold orbital ring, chrome and hot red with an electric-blue glow, flat vector, "
     "centered, symmetrical, badge composition, retro-futurist 1970s corporate identity, "
     "NO TEXT NO LETTERS NO WORDS."),
    ("juice", "1:1",
     "A single tall cup of intensely glowing electric-blue liquid on a white cafeteria table, "
     "volumetric glow, condensation, clinical overhead lighting, unsettlingly radiant, "
     "product photography for a retro-futurist corporate beverage, NO TEXT NO LETTERS."),
]


# Executive portraits. Corporate headshots played dead straight — the comedy is entirely in
# the bios underneath, so the images must not wink. A portrait that looks like a joke lets the
# reader off the hook before they reach "sends birthday coupons to customers marked deceased".
PORTRAIT_STYLE = (" Corporate executive headshot, neutral studio backdrop, confident pleasant "
                  "expression, retro-futurist corporate photography, crisp lighting, "
                  "shoulders-up, NO TEXT NO LETTERS NO WATERMARK.")

EXECS = [
    ("mara-venn", "A composed woman in her fifties in an immaculate deep-red executive suit, "
                  "silver pin shaped like an orbital ring, faint unwavering smile."),
    ("ivo-crumb", "A precise man in his forties in a white lab coat over a corporate shirt, "
                  "wire-rim glasses, holding a clipboard, pleasant clinical expression."),
    ("celeste-quark", "An elegant woman in her thirties in a chrome-accented blazer, "
                      "immaculate styling, standing in front of a mirrored wall."),
    ("harlan-scrip", "A genial heavyset man in his sixties in a pinstripe suit with a chrome "
                     "lapel badge, warm salesman smile that does not reach the eyes."),
    ("june-kestrel", "A severe woman in her fifties in a decorated navy-blue quasi-military "
                     "corporate uniform with orbital insignia, chin slightly raised."),
    ("pax-7", "A friendly humanoid customer-service robot with a smooth white ceramic face, "
              "a single warm blue optical band, wearing a small corporate necktie."),
]


def main() -> int:
    from mindbot_pipeline import imagery, models  # noqa: F401 — models loads .env
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("  no OPENROUTER_API_KEY")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    made = []

    print(f"\n  NOVA SPACE BURGERS — {len(ADS) + len(EXTRAS)} images\n")
    for slug, headline, prompt in ADS:
        p = OUT / f"ad-{slug}.png"
        if p.exists():
            print(f"   {slug:<16} cached")
            made.append((slug, "cached", headline))
            continue
        t = time.time()
        r = imagery.generate(prompt + ANCHOR, p, key, aspect="16:9")
        model = r.get("model", "?") if r["ok"] else "FAILED"
        print(f"   {slug:<16} {model[:34]:<34} {time.time() - t:>5.1f}s")
        made.append((slug, model, headline))

    for slug, aspect, prompt in EXTRAS:
        p = OUT / f"{slug}.png"
        if p.exists():
            print(f"   {slug:<16} cached")
            continue
        t = time.time()
        r = imagery.generate(prompt, p, key, aspect=aspect)
        print(f"   {slug:<16} {r.get('model', 'FAILED')[:34]:<34} {time.time() - t:>5.1f}s")

    (OUT / "team").mkdir(exist_ok=True)
    for slug, desc in EXECS:
        p = OUT / "team" / f"{slug}.png"
        if p.exists():
            print(f"   {slug:<16} cached")
            continue
        t = time.time()
        r = imagery.generate(desc + PORTRAIT_STYLE, p, key, aspect="1:1")
        print(f"   {slug:<16} {r.get('model', 'FAILED')[:34]:<34} {time.time() - t:>5.1f}s")

    try:
        from mindbot_pipeline.collaboration import ledger
        ledger("nova_campaign", f"{len(made)} advertisements generated from the brand bible",
               "nova")
    except Exception:  # noqa: BLE001
        pass

    print(f"\n   -> {OUT}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
