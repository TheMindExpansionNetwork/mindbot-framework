"""Consolidate the night shift's per-platform audit artifacts into one morning report.

Run by .github/workflows/nightly.yml. Reads the downloaded audit-*/. _audit_facts.json files and
writes a single markdown page you can read in ten seconds over coffee.

Design rule: a missing platform must be LOUDER than a passing one. The failure mode of any
nightly report is that it looks green because the job that would have gone red never ran.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_OS = ["ubuntu-latest", "macos-latest", "windows-latest"]
EXPECTED_PY = ["3.10", "3.11", "3.12", "3.13"]


def main(indir: str, outfile: str) -> int:
    root = Path(indir)
    rows = []
    for d in sorted(root.glob("audit-*")):
        f = d / "_audit_facts.json"
        # name shape: audit-<os>-py<version>
        rest = d.name[len("audit-"):]
        osname, _, py = rest.rpartition("-py")
        if not f.exists():
            rows.append({"os": osname, "py": py, "ok": False, "facts": {}, "why": "no artifact — the job did not finish"})
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            rows.append({"os": osname, "py": py, "ok": False, "facts": {}, "why": f"unreadable: {e}"})
            continue
        rows.append({"os": osname, "py": py, "ok": data.get("fail", 1) == 0,
                     "facts": data.get("facts", {}),
                     "why": "" if data.get("fail", 1) == 0 else f"{data.get('fail')} check(s) failed"})

    seen = {(r["os"], r["py"]) for r in rows}
    missing = [(o, p) for o in EXPECTED_OS for p in EXPECTED_PY if (o, p) not in seen]
    passed = sum(1 for r in rows if r["ok"])
    total = len(EXPECTED_OS) * len(EXPECTED_PY)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    verdict = "ALL GREEN" if (passed == total and not missing) else "NEEDS A LOOK"

    out = [f"# Night shift — {now}", ""]
    out.append(f"**{verdict}** — {passed}/{total} platform × version combinations passed the full audit.")
    out.append("")
    if os.environ.get("RUN_URL"):
        out.append(f"[Full run log]({os.environ['RUN_URL']})")
        out.append("")

    if missing:
        out.append(f"> **{len(missing)} combination(s) produced no result.** A silent gap is not a pass:")
        out.append("> " + ", ".join(f"`{o} py{p}`" for o, p in missing))
        out.append("")

    out += ["| Platform | Python | Result | Tests | Actions | Notes |", "|---|---|---|--:|--:|---|"]
    for r in sorted(rows, key=lambda r: (r["os"], r["py"])):
        fx = r["facts"]
        mark = "PASS" if r["ok"] else "**FAIL**"
        out.append(f"| {r['os']} | {r['py']} | {mark} | {fx.get('tests', '—')} | "
                   f"{fx.get('actions', '—')} | {r['why'] or ''} |")
    out.append("")

    posix = [r for r in rows if r["os"] != "windows-latest" and r["ok"]]
    if posix:
        out.append(f"**POSIX locking exercised:** {len(posix)} Linux/macOS run(s) passed the concurrency "
                   "suite with real subprocesses. This is the gap `docs/TEST_REPORT.md` names — "
                   "`fcntl.flock` is no longer assumed, it is executed nightly.")
        out.append("")

    out.append("## What this run does not establish")
    out.append("")
    out += [
        "- **No live model calls.** No API key is present in CI, so every model path ran in template",
        "  mode. This validates the machinery around the models, not the models.",
        "- **Not a security audit.** No dependency CVE scan, no fuzzing, no third-party review.",
        "- **Fresh checkout each run.** The ledger starts near-empty, so this exercises chain",
        "  *mechanics*, not the long-lived history in the committed ledger.",
        "",
        "<sub>Written by `framework/_nightly_report.py`. Every number above came from a job that ran;",
        "nothing here is asserted by hand.</sub>",
    ]

    Path(outfile).write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{verdict}: {passed}/{total} passed, {len(missing)} missing -> {outfile}")
    return 0          # never fail the report step; the audit jobs are the gate


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "_nightly",
                  sys.argv[2] if len(sys.argv) > 2 else "NIGHTLY.md"))
