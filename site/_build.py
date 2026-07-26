"""SITE BUILD — render the public docs into the site with one consistent shell.

WHY RENDER THEM HERE INSTEAD OF LINKING TO GITHUB
  Linking a white paper to github.com/.../WHITEPAPER.md throws the reader out of the site,
  into a UI that looks like a code review, on a page that is 40% chrome. People do not come
  back. Rendering them here keeps the whole thing one artifact with one design, works offline,
  and means the docs get the same care as the landing page.

WHAT IT DOES
  * converts each doc in PAGES to site/docs/<slug>.html inside a shared shell
  * builds site/docs/index.html — a reading room, grouped by intent
  * rewrites .md links between docs so they resolve on the site
  * fails loudly on a missing source, because a docs index with a dead link is worse than
    an index with fewer entries

RUN
    python site/_build.py
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = Path(__file__).resolve().parent / "docs"

# Grouped by what the reader is trying to do, not alphabetically. Order is the reading order.
PAGES = [
    ("Start here", [
        ("WHAT_THIS_ACTUALLY_IS.md", "What this actually is",
         "The plain-English version. Ten counselors, one that's yours, and what 'autonomous' honestly means."),
        ("FIVE_MINUTES.md", "MindBot in 5 minutes",
         "Install, meet it, make something, check the receipt."),
        ("THE_BALLAD_OF_THE_ELEVEN.md", "The Ballad of the Eleven",
         "The manual, in verse. Every parenthetical is a real measurement."),
    ]),
    ("The argument", [
        ("WHITEPAPER.md", "Verifiable Autonomy",
         "The white paper. Why three integrity layers are needed and why the third is the one nobody ships."),
        ("PROOF_OF_AUTONOMY.md", "Proof of autonomy",
         "How the chain, the Merkle root and the anchors actually work."),
        ("WHY_DIFFERENT.md", "Why this is different",
         "The six self-* properties, each a command you can run."),
        ("POSITIONING.md", "Positioning",
         "The slogan, the competitive argument, objection handling, and words we refuse to use."),
    ]),
    ("Build with it", [
        ("MODS.md", "Mods",
         "Capability-scoped plugins the runtime audits against their own manifest."),
        ("THE_OFFICE.md", "The Office",
         "Running it unattended — the scheduled shift, and every guard around it."),
        ("BUDGET.md", "Budget",
         "Spend ceilings enforced before the call, not tallied after the invoice."),
        ("MODEL_LINEUP.md", "Model lineup",
         "Which model sits in which seat, and what each one costs."),
    ]),
    ("Evidence", [
        ("TEST_REPORT.md", "Test report",
         "20/20 subsystem checks, 177 tests — including what it does NOT establish."),
        ("CASE_STUDY_THE_FIRM.md", "Case study: The Firm",
         "Hierarchical routing down a cost pyramid, measured."),
        ("AUTONOMY_READINESS.md", "Autonomy readiness",
         "What has to be true before you leave it running."),
        ("SLOGANS.md", "Slogans",
         "Launch language, and the claims we retired for being unprovable."),
    ]),
]

SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>{title} — MindBot</title>
<meta name="description" content="{desc}">
<link rel="icon" href="../assets/logo.png">
<style>
:root{{--bg:#0B0B14;--bg2:#12102A;--panel:#151429;--line:#282348;--ink:#F2EEFF;
  --muted:#8F88C4;--accent:#6E5BFF;--green:#32E6A0;--amber:#FFC857}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{background:radial-gradient(110% 60% at 78% -10%,var(--bg2),var(--bg)) fixed;color:var(--ink);
  font:17px/1.72 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  -webkit-font-smoothing:antialiased}}
a{{color:var(--accent);text-decoration:none}} a:hover{{text-decoration:underline}}
img{{max-width:100%;height:auto;border-radius:12px}}
nav{{position:sticky;top:0;z-index:20;backdrop-filter:blur(14px);background:rgba(11,11,20,.85);
  border-bottom:1px solid var(--line)}}
nav .in{{max-width:860px;margin:auto;padding:0 22px;height:58px;display:flex;align-items:center;gap:16px}}
nav img{{width:26px;border-radius:0}} nav b{{letter-spacing:.14em;font-size:13px}}
nav .r{{margin-left:auto;display:flex;gap:18px;font-size:13.5px}}
nav .r a{{color:var(--muted)}} nav .r a:hover{{color:var(--ink);text-decoration:none}}
main{{max-width:860px;margin:0 auto;padding:56px 22px 96px}}
h1{{font-size:clamp(2.1rem,6vw,3.3rem);letter-spacing:-.035em;line-height:1.05;margin:0 0 26px}}
h2{{font-size:1.62rem;letter-spacing:-.02em;margin:52px 0 14px;padding-top:14px;border-top:1px solid var(--line)}}
h3{{font-size:1.2rem;margin:32px 0 10px;color:#D6D0FA}}
h4{{font-size:1.02rem;margin:22px 0 8px;color:var(--muted)}}
p,li{{margin-bottom:14px}}
ul,ol{{padding-left:24px;margin-bottom:16px}}
li::marker{{color:var(--accent)}}
strong{{color:#fff}} em{{color:#D6D0FA}}
hr{{border:0;border-top:1px solid var(--line);margin:44px 0}}
blockquote{{border-left:3px solid var(--accent);padding:4px 0 4px 20px;margin:22px 0;color:#D6D0FA}}
blockquote p:last-child{{margin-bottom:0}}
code{{background:#0A0918;border:1px solid var(--line);border-radius:6px;padding:2px 6px;
  font:13.5px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--green)}}
pre{{background:#0A0918;border:1px solid var(--line);border-radius:12px;padding:18px;
  overflow-x:auto;margin:20px 0}}
pre code{{background:none;border:0;padding:0;color:#C9C2FF;font-size:13px;line-height:1.6}}
table{{width:100%;border-collapse:collapse;margin:22px 0;font-size:15px;display:block;overflow-x:auto}}
th,td{{border:1px solid var(--line);padding:10px 13px;text-align:left;vertical-align:top}}
th{{background:var(--panel);color:var(--muted);font-size:12.5px;letter-spacing:.05em;
  text-transform:uppercase;font-weight:700}}
details{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:20px 0}}
summary{{cursor:pointer;font-weight:600}}
.back{{display:inline-block;margin-bottom:30px;color:var(--muted);font-size:14px}}
footer{{border-top:1px solid var(--line);margin-top:70px;padding:36px 22px 60px;text-align:center;
  color:var(--muted);font-size:13.5px}}
footer .s{{font-size:1.15rem;font-weight:800;color:var(--ink);margin-bottom:10px}}
</style>
</head>
<body>
<nav><div class="in">
  <a href="../index.html"><img src="../assets/logo.png" alt=""></a>
  <b>MINDBOT</b>
  <div class="r">
    <a href="index.html">Docs</a>
    <a href="../demo/chain-check.html">Game</a>
    <a href="../demo/guide.html">Guide</a>
    <a href="https://github.com/TheMindExpansionNetwork/mindbot-framework">GitHub</a>
  </div>
</div></nav>
<main>
<a class="back" href="index.html">← all docs</a>
{body}
</main>
<footer>
  <div class="s">Prove, don't promise.</div>
  <a href="../index.html">mindbot</a> · <a href="index.html">docs</a> ·
  <a href="https://github.com/TheMindExpansionNetwork/mindbot-framework">source</a>
</footer>
</body>
</html>
"""


def slug(name: str) -> str:
    return name.replace(".md", "").lower().replace("_", "-")


def render(md_text: str, known: dict) -> str:
    import markdown
    body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "toc", "attr_list", "sane_lists", "md_in_html"],
    )
    # Rewrite inter-doc links so they resolve on the site. Docs link to each other as
    # `FIVE_MINUTES.md` or `../NOTES.md`; the first should become a page here, and the second
    # points at something we deliberately do not publish, so it goes to GitHub instead.
    def fix(m):
        href = m.group(1)
        if href.startswith(("http", "#", "mailto:")):
            return m.group(0)
        base = href.split("/")[-1]
        if base in known:
            return f'href="{slug(base)}.html"'
        # ANY other relative path points at the repo, not the site. The docs link to source
        # files, folders and images that were never copied here — leaving those alone produced
        # two 404s the link checker caught (`../mods/hello-world/`, an image under apps/promo).
        # A tree URL for directories, blob for files.
        clean = href.lstrip("./")
        kind = "tree" if href.endswith("/") else "blob"
        return (f'href="https://github.com/TheMindExpansionNetwork/mindbot-framework/'
                f'{kind}/main/{clean}"')
    body = re.sub(r'href="([^"]+)"', fix, body)

    # IMAGES GET COPIED, NOT LINKED. A GitHub blob URL does not render in an <img>, and a raw
    # URL makes the page depend on github.com being reachable — so a doc that referenced
    # apps/promo/assets/firm_hierarchy.png shipped a broken image. Pull the file in instead.
    def fix_img(m):
        src = m.group(1)
        if src.startswith(("http", "data:")):
            return m.group(0)
        found = (DOCS / src).resolve()
        if not found.is_file():
            found = (ROOT / src.lstrip("./")).resolve()
        if not found.is_file():
            return m.group(0)                      # leave it; the link checker will report it
        dest = OUT / "img" / found.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(found, dest)
        return f'src="img/{found.name}"'

    return re.sub(r'src="([^"]+)"', fix_img, body)


def build() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    known = {f for _, items in PAGES for f, _, _ in items}
    missing, built = [], []

    for _group, items in PAGES:
        for fname, title, blurb in items:
            src = DOCS / fname
            if not src.is_file():
                missing.append(fname)
                continue
            page = render(src.read_text(encoding="utf-8"), known)
            (OUT / f"{slug(fname)}.html").write_text(
                SHELL.format(title=html.escape(title), desc=html.escape(blurb), body=page),
                encoding="utf-8")
            built.append((fname, title))

    if missing:
        # Loud, not silent: an index that quietly drops a page is how a doc goes unpublished
        # for a month without anyone noticing.
        print("  MISSING SOURCES — not published:")
        for m in missing:
            print(f"    docs/{m}")
        return 1

    # the reading room
    cards = []
    for group, items in PAGES:
        rows = "\n".join(
            f'<a class="doc" href="{slug(f)}.html"><h4>{html.escape(t)}</h4>'
            f'<p>{html.escape(b)}</p></a>' for f, t, b in items)
        cards.append(f'<h2>{html.escape(group)}</h2><div class="docs">{rows}</div>')

    index_body = f"""
<h1>Documentation</h1>
<p style="color:var(--muted);max-width:60ch">Everything, in reading order. The white paper is the
cold version; <a href="what-this-actually-is.html">What this actually is</a> is the one to read
first if you just want to understand the thing.</p>
<style>
.docs{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px;margin:18px 0 8px}}
a.doc{{display:block;background:var(--panel);border:1px solid var(--line);border-radius:14px;
  padding:20px;text-decoration:none;transition:border-color .15s,transform .15s}}
a.doc:hover{{border-color:var(--accent);transform:translateY(-2px);text-decoration:none}}
a.doc h4{{margin:0 0 6px;color:var(--ink);font-size:1.05rem}}
a.doc p{{margin:0;color:var(--muted);font-size:.9rem;line-height:1.5}}
</style>
{''.join(cards)}
<h2>Also</h2>
<div class="docs">
  <a class="doc" href="../demo/chain-check.html"><h4>Chain Check</h4>
    <p>A 60-second game about spotting a broken hash chain. Real SHA-256.</p></a>
  <a class="doc" href="../demo/guide.html"><h4>Trust, tested</h4>
    <p>The interactive guide — break a live chain yourself.</p></a>
  <a class="doc" href="https://github.com/TheMindExpansionNetwork/mindbot-starters"><h4>Starters</h4>
    <p>Four small projects, each teaching one thing.</p></a>
  <a class="doc" href="https://github.com/TheMindExpansionNetwork/mindbot-framework/blob/main/AGENTS.md">
    <h4>AGENTS.md</h4><p>The contract, written for an AI working in the repo.</p></a>
</div>
"""
    (OUT / "index.html").write_text(
        SHELL.format(title="Documentation", desc="Every MindBot document, in reading order.",
                     body=index_body).replace('<a class="back" href="index.html">← all docs</a>',
                                              '<a class="back" href="../index.html">← home</a>'),
        encoding="utf-8")

    print(f"\n  {len(built)} pages -> site/docs/")
    for f, t in built:
        print(f"    {slug(f) + '.html':<32} {t}")
    print(f"    {'index.html':<32} the reading room\n")
    return 0


if __name__ == "__main__":
    sys.exit(build())
