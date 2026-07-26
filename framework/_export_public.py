"""EXPORT â€” build the public framework release from this private working repo.

WHY AN EXPORT AND NOT `gh repo edit --visibility public`
  This repo is a workshop. It holds a 900-entry ledger of real work, internal task lists,
  business planning, a personal runbook, and â€” discovered while preparing to publish â€” a live
  API key sitting in git history as a test fixture. You cannot delete something from git
  history by editing a file; the only real options are rewriting history or starting clean.

  So the public repo gets FRESH HISTORY containing only what a framework release should have.
  That fixes the key permanently, keeps the workshop private, and means the first thing anyone
  sees is a clean project rather than someone's TODO list.

  Re-runnable: as the framework evolves, run this again and force-push. The private repo stays
  the source of truth.

WHAT IS DELIBERATELY LEFT BEHIND
  * collaboration/  â€” the ledger is USER DATA. A fresh install must start with an empty chain,
                      or every user inherits our history and `verify` means nothing to them.
  * NOTES / TOMORROW / HANDOFF / LAUNCH_*  â€” operational and personal.
  * docs/BUSINESS_* , docs/HERMES_* , docs/plans/ â€” commercial planning.
  * runtime output   â€” outbox, studio, observations, voice_out, firm_runs, spend.jsonl, .env

RUN
    python framework/_export_public.py --to Z:\MINDBOT-PUBLIC
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Copied wholesale (minus the prune list below).
# `lore/` ships: the canon, the vows and the counselor personas ARE the framework's identity,
# not private notes. `collaboration/` does NOT ship â€” see SEED_FILES for the one exception.
DIRS = ["framework", "mods", "apps", "assets", "lore", ".github", ".devcontainer"]

# Individual files pulled out of otherwise-private directories because the code needs them.
# Found by the verification step below: two tests failed on a fresh export because
# `lore/` and `collaboration/missions.json` were missing. That is precisely why this script
# runs the suite against the EXPORT rather than trusting the source repo's green tests.
SEED_FILES = {
    "collaboration/missions.json": "collaboration/missions.json",
}

FILES = [
    "README.md", "AGENTS.md", "LICENSE", "SECURITY.md", "CHANGELOG.md",
    "vps-install.sh", "install.sh", ".gitignore",
]

# Only these docs ship. An allow-list, not a deny-list: a new internal doc must be explicitly
# added to become public, which is the safe direction for that mistake to fail in.
DOCS = [
    "WHITEPAPER.md", "FIVE_MINUTES.md", "POSITIONING.md", "SLOGANS.md",
    "PROOF_OF_AUTONOMY.md", "MODS.md", "BUDGET.md", "MODEL_LINEUP.md",
    "WHY_DIFFERENT.md", "THE_OFFICE.md", "THE_BALLAD_OF_THE_ELEVEN.md",
    "TEST_REPORT.md", "AUTONOMY_READINESS.md", "CASE_STUDY_THE_FIRM.md",
]

# Removed after copying. Runtime output and anything machine-specific.
PRUNE = [
    "framework/.env", "framework/.env.bak", "framework/spend.jsonl",
    "framework/outbox", "framework/studio", "framework/observations",
    "framework/voice_out", "framework/firm_runs", "framework/_audit_facts.json",
    "framework/.free_models_cache.json", "apps/intro_video/out",
    "framework/mindbot_pipeline/.free_models_cache.json",
]

PRUNE_GLOBS = ["**/__pycache__", "**/*.pyc", "**/.pytest_cache", "**/*.wav", "**/*.mp4"]

# Artifacts the VERIFICATION RUN itself creates inside the export. Running the suite exercises
# the framework, which writes a ledger, a dashboard render and dataset output â€” so a naive
# "clean then verify" order ships those. Caught by inspecting the finished export and finding a
# collaboration/ledger.jsonl that had never existed in the source copy.
# Everything here is pruned AFTER the tests, never before.
POST_TEST_PRUNE = [
    "collaboration/ledger.jsonl", "collaboration/ledger.jsonl.head",
    "collaboration/ledger.jsonl.lock", "collaboration/trails.jsonl",
    "collaboration/ANCHORS.jsonl", "dashboard/output", "dataset",
    "framework/spend.jsonl", "framework/observations", "framework/studio",
    "framework/outbox", "framework/voice_out", "framework/firm_runs",
    "framework/_audit_facts.json",
]

# Belt and braces: refuse to publish if any of these appear in the exported tree.
FORBIDDEN = [
    (re.compile(r"sk-or-v1-(?!0123456789|xxx|YOUR|\.\.\.)[A-Za-z0-9]{20,}"), "live OpenRouter key"),
    (re.compile(r"\b(?:ak|as|wk|ws)-[A-Za-z0-9]{20,}"), "Modal token"),
    (re.compile(r"sk-ant-(?!api03-abcdef)[A-Za-z0-9_-]{20,}"), "Anthropic key"),
    (re.compile(r"ghp_(?!abcdefghij)[A-Za-z0-9]{30,}"), "GitHub token"),
]


def _wipe_keeping_git(dst: Path) -> None:
    """Empty the export dir but PRESERVE .git.

    Two reasons this is not a plain rmtree:
      1. A re-export should update the working tree and let git show the diff. Deleting .git
         throws away the remote, the history, and any published commit â€” turning every refresh
         into a force-push of unrelated history.
      2. `shutil.rmtree(ignore_errors=True)` silently FAILS on git's object store, because git
         marks those files read-only on Windows. The directory then still exists, mkdir raises
         FileExistsError, and the error you see has nothing to do with the real cause.
    """
    import stat

    def force(func, path, _exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    for p in dst.iterdir():
        if p.name == ".git":
            continue
        if p.is_dir():
            shutil.rmtree(p, onerror=force)
        else:
            p.chmod(stat.S_IWRITE)
            p.unlink()


def copy(dst: Path) -> None:
    if dst.exists():
        _wipe_keeping_git(dst)
    dst.mkdir(parents=True, exist_ok=True)

    for d in DIRS:
        src = ROOT / d
        if src.is_dir():
            shutil.copytree(src, dst / d, dirs_exist_ok=True)
    for f in FILES:
        if (ROOT / f).is_file():
            shutil.copy2(ROOT / f, dst / f)

    for src_rel, dst_rel in SEED_FILES.items():
        s = ROOT / src_rel
        if s.is_file():
            (dst / dst_rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, dst / dst_rel)

    (dst / "docs").mkdir(exist_ok=True)
    for name in DOCS:
        p = ROOT / "docs" / name
        if p.is_file():
            shutil.copy2(p, dst / "docs" / name)

    # .env.example is the one dotfile users need; copytree already brought it, but be explicit.
    ex = ROOT / "framework" / ".env.example"
    if ex.is_file():
        shutil.copy2(ex, dst / "framework" / ".env.example")

    for rel in PRUNE:
        p = dst / rel
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    for pat in PRUNE_GLOBS:
        for p in dst.glob(pat):
            shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)


def audit(dst: Path) -> list[str]:
    """Refuse to publish a tree containing anything that looks like a live credential."""
    hits = []
    for p in dst.rglob("*"):
        if not p.is_file() or p.suffix in (".png", ".jpg", ".wav", ".mp4", ".zip"):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat, label in FORBIDDEN:
            for m in pat.finditer(text):
                hits.append(f"{p.relative_to(dst)}: {label} â€” {m.group(0)[:18]}â€¦")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--to", required=True)
    args = ap.parse_args()
    dst = Path(args.to)

    print(f"\n  exporting -> {dst}")
    copy(dst)

    files = [p for p in dst.rglob("*") if p.is_file()]
    print(f"  {len(files)} files copied")

    print("\n  credential auditâ€¦")
    hits = audit(dst)
    if hits:
        print("  REFUSING TO PUBLISH â€” found:")
        for h in hits[:20]:
            print(f"    {h}")
        return 1
    print("  clean â€” no live credentials in the exported tree")

    # Prove the export actually works before anyone clones it.
    print("\n  verifying the exported framework runsâ€¦")
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "tests"],
                       cwd=dst / "framework", capture_output=True, text=True, timeout=900)
    line = next((l for l in r.stderr.splitlines() if l.startswith("Ran ")), "?")
    print(f"  {line.strip()} â€” {'OK' if r.returncode == 0 else 'FAILED'}")
    if r.returncode != 0:
        print(r.stderr[-1500:])
        return 1

    # NOW clean up what the tests just created. Order matters: prune-then-verify would ship
    # a ledger, a dashboard render and dataset output that the suite wrote on its way through.
    print("\n  removing artifacts the test run createdâ€¦")
    removed = 0
    for rel in POST_TEST_PRUNE:
        p = dst / rel
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
            removed += 1
        elif p.exists():
            p.unlink()
            removed += 1
    for pat in PRUNE_GLOBS:
        for p in dst.glob(pat):
            shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
    print(f"  {removed} runtime artifact(s) removed")

    # Re-audit AFTER the tests, because a test run could in principle write a secret.
    hits = audit(dst)
    if hits:
        print("  REFUSING TO PUBLISH â€” post-test audit found:")
        for h in hits[:20]:
            print(f"    {h}")
        return 1
    print("  post-test audit clean")

    left = sorted(p.relative_to(dst).as_posix() for p in dst.rglob("*")
                  if p.is_file() and p.suffix in (".jsonl",))
    if left:
        print(f"  note â€” .jsonl files remaining: {left}")

    print(f"\n  ready. next:")
    print(f"    cd {dst} && git init && git add -A && git commit && git push --force\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

