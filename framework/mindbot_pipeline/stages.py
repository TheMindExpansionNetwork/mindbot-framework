"""Stage handlers — mechanical pipeline work that runs WITHOUT a model.

These are what make the 15-minute pulse real even on a machine with no API key:
intake scans, dataset stats, handoff mining, dashboard refresh. Generative work
routes to counselors with brains attached; mechanical work just runs.

A handler: fn(task_text, state) -> (draft_markdown, detail). Matched by keyword.

Extend: add a stage -> write a handler with that signature, then append a
(keywords_tuple, fn) row to HANDLERS. match_handler picks the first row whose
any keyword is a substring of the (lowercased) task text, so order = priority.
Drafts return markdown only; nothing here transmits — the human approves the outbox.
"""

import json
import re
from pathlib import Path

from .collaboration import DATASET_OUT, HANDOFF_PATH, PIPE_DIR, ROOT, read_tasks

DATASET_MANIFEST = DATASET_OUT / "MANIFEST.json"
HANDOFF = HANDOFF_PATH


SKIP_DIRS = {"venv", ".venv", ".git", "node_modules", "__pycache__", ".idea"}


def _walk(folder):
    """Fast walk that skips heavy non-asset dirs."""
    import os
    n_files, size = 0, 0
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            n_files += 1
            try:
                size += (Path(dirpath) / fn).stat().st_size
            except OSError:
                pass
    return n_files, size


def intake_scan(task_text, state):
    """Walk 01_-17_ and produce a fresh manifest of what exists."""
    rows = []
    for child in sorted(ROOT.iterdir()):
        if child.is_dir() and re.match(r"\d{2}_", child.name):
            n_files, size = _walk(child)
            rows.append((child.name, n_files, size // 1_000_000))
    manifest = {"folders": [{"name": n, "files": f, "mb": m} for n, f, m in rows]}
    out = PIPE_DIR / "intake_manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    draft = "# Intake scan\n" + "\n".join(f"- {n}: {f} files, {m} MB" for n, f, m in rows)
    return draft, f"manifest → {out.name}"


def dataset_stats(task_text, state):
    """Report the 15_ corpus state — counts, categories, splits."""
    if not DATASET_MANIFEST.exists():
        return "[NEED: 15_ manifest — run generate_dataset.py first]", "manifest missing"
    m = json.loads(DATASET_MANIFEST.read_text(encoding="utf-8"))
    # prefer the held-out count; fall back to older manifests that lack the split
    gold = m.get("gold_seeds_heldout", m.get("gold_seeds", "?"))
    draft = ("# Dataset status\n"
             f"- total {m['total']} (train {m['train']} / val {m['validation']} / test {m['test']})\n"
             f"- gold seeds (held out): {gold}\n" +
             "\n".join(f"- {k}: {v}" for k, v in sorted(m["categories"].items())))
    return draft, "dataset stats compiled"


def handoff_mine(task_text, state):
    """Mine recent handoffs for gap lines → candidate TODO items (drafted, not auto-added)."""
    if not HANDOFF.exists():
        return "[NEED: handoff file]", "missing"
    text = HANDOFF.read_text(encoding="utf-8")[:20000]
    gaps = re.findall(r"(?:Noticed|gap → task)[:\*]*\s*(.+)", text)
    blockers = re.findall(r"\*\*Blockers:?\*\*:?\s*(.+)", text)
    draft = ("# Handoff mining\n## Gap candidates (review before adding to TODO)\n" +
             "\n".join(f"- {g.strip()[:140]}" for g in gaps[:10] or ["(none found)"]) +
             "\n## Standing blockers\n" +
             "\n".join(f"- {b.strip()[:140]}" for b in blockers[:10] or ["(none)"]))
    return draft, f"{len(gaps)} gaps, {len(blockers)} blockers mined"


def todo_groom(task_text, state):
    """Summarize TODO health for the tracker."""
    tasks = read_tasks()
    stale = [t for t in tasks if t["in_progress"]]
    draft = ("# TODO grooming\n"
             f"- {sum(t['done'] for t in tasks)} done, "
             f"{sum(1 for t in tasks if not t['done'])} open, {len(stale)} claimed-in-progress\n" +
             "\n".join(f"- IN PROGRESS: {t['text'][:100]} (claimed by {t['claimed_by']})" for t in stale[:8]))
    return draft, "groomed"


def skill_dreamer(task_text, state):
    """Dream a new skill: scaffold a SKILL.md draft from a gap the council noticed.

    Mechanical half (here): mine handoff gaps + repeated TODO themes, pick the most
    recurrent un-skilled action, scaffold the SKILL.md with status: dreamed.
    Generative half (a counselor with a model): fills the steps, test-runs, promotes.
    """
    skills_dir = PIPE_DIR / "skills"
    existing = {p.parent.name for p in skills_dir.glob("*/SKILL.md")}
    text = HANDOFF.read_text(encoding="utf-8")[:30000] if HANDOFF.exists() else ""
    gaps = re.findall(r"(?:Noticed|gap → task)[:\*]*\s*(.+)", text)
    candidates = [g.strip() for g in gaps if len(g.strip()) > 30][:5]
    if not candidates:
        return "No fresh gaps to dream a skill from tonight — the council noticed nothing un-skilled.", "no candidates"
    seed = candidates[0]
    # slug = first 4 alnum words of the gap; guard against re-dreaming a slug we already scaffolded
    slug = "-".join(re.findall(r"[a-z0-9]+", seed.lower())[:4]) or "dreamed-skill"
    if slug in existing:
        return f"Skill '{slug}' already exists; dreaming skipped.", "duplicate"
    out = skills_dir / slug
    out.mkdir(parents=True, exist_ok=True)
    (out / "SKILL.md").write_text(
        f"---\nname: {slug}\ndescription: [NEED: one-line trigger — dreamed from gap: "
        f"{seed[:120]}]\nstatus: dreamed\n---\n\n# {slug}\n\n## Dreamed from\n{seed}\n\n"
        f"## Steps\n1. [NEED: a counselor with a model fills and test-runs this]\n\n"
        f"## Output contract\n[NEED]\n", encoding="utf-8")
    return f"# Skill dreamed\nNew draft skill `{slug}` scaffolded from gap:\n> {seed}\n\nNeeds a counselor test-run before status: active.", f"dreamed {slug}"


def night_shift(task_text, state):
    """Night Shift: queue translation/promo drafts for other timezones. Drafts only."""
    targets = state.get("night_shift", {}).get("languages", ["[NEED: languages — set state.night_shift.languages]"])
    outbox = PIPE_DIR / "outbox"
    outbox.mkdir(exist_ok=True)
    draft = ("# Night Shift queue\n"
             f"Target languages/timezones: {', '.join(targets)}\n\n"
             "Queued for a model-backed counselor:\n"
             "1. Translate the week's top stream clip descriptions + collective invite.\n"
             "2. Draft collab pitches to 3 international creative communities [NEED: human shortlist].\n"
             "3. Schedule-ready post drafts for foreign-prime-time (NOTHING auto-posts).\n\n"
             "Constitution: all of this lands in outbox/ for the 07:00 review. The sun\n"
             "never catches this system having sent anything by itself.")
    return draft, f"night shift queued for {len(targets)} targets"


def watchtower(task_text, state):
    """The focus guard. Releases claims stuck >12h, flags off-focus tasks, counts drift.

    The Watchtower says it out loud — including to the founder. Sleeps never, gladly.
    """
    import datetime
    from .collaboration import TODO_PATH
    if not TODO_PATH.exists():
        return "[NEED: TODO file]", "missing"
    now = datetime.datetime.now()
    lines = TODO_PATH.read_text(encoding="utf-8").splitlines()
    released, flagged = [], []
    focus_words = set(re.findall(r"[a-z]{4,}", state.get("focus", {}).get("mission", "").lower()))
    for i, line in enumerate(lines):
        # cross-module contract: this pattern must match exactly how claims are written
        # into the TODO ("- [~] (claimed: who YYYY-MM-DD HH:MM) text") or releases silently no-op
        m = re.match(r"^- \[~\] \(claimed: (\S+) (\d{4}-\d{2}-\d{2} \d{2}:\d{2})\) (.+)$", line.strip())
        if m:
            who, ts, text = m.groups()
            try:
                age_h = (now - datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M")).total_seconds() / 3600
            except ValueError:
                continue
            if age_h > 12:
                lines[i] = f"- [ ] {text} *(claim by {who} released after {age_h:.0f}h — Watchtower)*"
                released.append(f"{who}: {text[:70]}")
        m2 = re.match(r"^- \[ \] (.+)$", line.strip())
        if m2 and focus_words:
            task_words = set(re.findall(r"[a-z]{4,}", m2.group(1).lower()))
            # flag only substantial tasks (>4 words) with zero overlap — avoids dinging terse items
            if task_words and not (task_words & focus_words) and len(task_words) > 4:
                flagged.append(m2.group(1)[:70])
    if released:
        TODO_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    draft = ("# Watchtower report\n"
             f"## Stuck claims released ({len(released)})\n" +
             "\n".join(f"- {r}" for r in released or ["(none — clean board)"]) +
             f"\n## Possibly off-focus ({len(flagged[:8])} shown — drift is a choice, make it on purpose)\n" +
             "\n".join(f"- {f}" for f in flagged[:8] or ["(nothing drifting)"]))
    return draft, f"released {len(released)}, flagged {len(flagged)}"


HANDLERS = [
    (("intake", "scan the workspace", "manifest"), intake_scan),
    (("dataset stats", "corpus status", "15_ status"), dataset_stats),
    (("mine the", "handoff mining", "mine handoffs"), handoff_mine),
    (("groom", "todo health", "tracker refresh"), todo_groom),
    (("dream a skill", "skill dream", "new skill from gap"), skill_dreamer),
    (("night shift", "translate", "international promo"), night_shift),
    (("watchtower", "focus guard", "stuck claims", "drift check"), watchtower),
]


def match_handler(task_text: str):
    lowered = task_text.lower()
    for keywords, fn in HANDLERS:
        if any(k in lowered for k in keywords):
            return fn
    return None
