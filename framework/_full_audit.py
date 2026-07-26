"""FULL SYSTEM AUDIT — exercise every subsystem and report measured facts.

Run before a release. Everything here is READ-ONLY or uses temp dirs; it does not spend money
and does not mutate the real ledger except via the normal (already-audited) paths.
"""
import io
import json
import os
import subprocess
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

FW = Path(__file__).resolve().parent
R = {"pass": 0, "fail": 0, "facts": {}}


def _utf8_env():
    """Force UTF-8 on subprocesses.

    The CLI prints ✓/✗/emoji. On Windows CI the default console encoding is cp1252, so those
    characters raise UnicodeEncodeError, the subprocess dies, and stdout comes back EMPTY — which
    the audit then reports as a failing check for an entirely cosmetic reason. Measured on
    windows-latest/py3.13: the secret scan showed FAIL with a blank detail while the scan itself
    had actually passed.
    """
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def check(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:  # noqa: BLE001
        ok, detail = False, f"{type(e).__name__}: {e}"
    R["pass" if ok else "fail"] += 1
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<44} {detail}")
    return ok


def main():
    print("\n=== 1. TEST SUITE ===")
    t = time.time()
    p = subprocess.run([sys.executable, "-m", "unittest", "discover", "tests"],
                       cwd=FW, capture_output=True, text=True, env=_utf8_env())
    line = [l for l in p.stderr.splitlines() if l.startswith("Ran ")]
    n = int(line[0].split()[1]) if line else 0
    R["facts"]["tests"] = n
    R["facts"]["test_secs"] = round(time.time() - t, 1)
    check("unit tests", lambda: (p.returncode == 0, f"{n} tests, {R['facts']['test_secs']}s"))

    print("\n=== 2. PROOF-OF-AUTONOMY ===")
    from mindbot_pipeline import provenance, notary
    v = provenance.verify()
    a = provenance.attest()
    au = notary.audit()
    R["facts"].update(actions=a["actions_recorded"], anchors=a["anchors"],
                      merkle=a["merkle_root"], violations=a["autonomous_external_actions"])
    check("ledger chain intact", lambda: (v["intact"], f"{v['entries']} entries"))
    check("externally verified", lambda: (a["externally_verified"],
                                          f"{a['anchors']} anchors, all match={au['all_match']}"))
    check("zero autonomous sends/charges", lambda: (a["autonomous_external_actions"] == 0,
                                                    str(a["autonomous_external_actions"])))
    pr = notary.prove(max(1, a["last_seq"] // 2))
    check("inclusion proof verifies", lambda: (notary.check_proof(pr),
                                               f"{len(pr['path'])} sibling hashes of {pr['total_entries']}"))

    print("\n=== 3. BUDGET GOVERNOR ===")
    from mindbot_pipeline import budget
    b = budget.status()
    R["facts"]["budget_caps"] = b["caps"]
    check("enforced by default", lambda: (b["enabled"], f"caps {b['caps']}"))
    check("free models cost nothing",
          lambda: (budget.price_of("x/y:free") == (0.0, 0.0), "$0"))
    check("unknown model billed pessimistically",
          lambda: (budget.price_of("who/knows") == budget.UNKNOWN_PRICE, str(budget.UNKNOWN_PRICE)))

    print("\n=== 4. MODS (capability system) ===")
    from mindbot_pipeline import mods
    found = mods.discover()
    R["facts"]["mods"] = len(found)
    check("hello-world present + audit clean",
          lambda: (any(m["slug"] == "hello-world" and m["ok"] for m in found),
                   f"{len(found)} mod(s)"))
    api, meta, findings = mods.load("hello-world", strict=True)
    check("static audit finds no overreach", lambda: (findings == [], f"perms={meta['permissions']}"))
    res = mods.run("hello-world", "overreach")
    check("undeclared capability DENIED",
          lambda: (not res["ok"] and "CapabilityDenied" in (res["error"] or ""), "refused + recorded"))

    print("\n=== 5. SECRET REDACTION ===")
    from mindbot_pipeline import redact
    check("catches provider keys",
          lambda: (bool(redact.scan("sk-or-v1-" + "a" * 40)), "openrouter shape"))
    check("no false positive on our own hashes",
          lambda: (redact.scan("merkle " + "a" * 64 + " commit abc1234") == [], "clean"))
    check("ledger write path scrubs",
          lambda: ("REDACTED" in redact.scrub("k=sk-ant-" + "b" * 30)[0], "masked"))

    print("\n=== 6. IDENTITY (self-model) ===")
    from mindbot_pipeline import identity
    w = identity.whoami()
    R["facts"].update(commands=w["capabilities"]["command_count"],
                      counselors=len(w["capabilities"]["counselors"]),
                      limits=len(w["limits"]))
    check("capabilities introspected", lambda: (w["capabilities"]["command_count"] > 20,
                                                f"{w['capabilities']['command_count']} commands"))
    check("states it is not conscious",
          lambda: ("not conscious" in " ".join(w["limits"]).lower(), f"{len(w['limits'])} limits"))

    print("\n=== 7. HTTP API ===")
    from mindbot_pipeline.server import ROUTES
    bad = []
    for name, fn in ROUTES.items():
        try:
            json.dumps(fn())
        except Exception as e:  # noqa: BLE001
            bad.append(f"{name}:{type(e).__name__}")
    R["facts"]["api_routes"] = len(ROUTES)
    check("every route returns JSON", lambda: (not bad, f"{len(ROUTES)} routes" + (f" BAD={bad}" if bad else "")))

    print("\n=== 8. CLI SURFACE ===")
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            from mindbot_pipeline import cli
    except Exception:  # noqa: BLE001
        pass
    src = (FW / "mindbot_pipeline" / "cli.py").read_text(encoding="utf-8")
    import re
    cmds = sorted(set(re.findall(r'add_parser\(\s*"([a-z][a-z0-9-]*)"', src)))
    R["facts"]["cli_commands"] = len(cmds)
    check("commands registered", lambda: (len(cmds) > 40, f"{len(cmds)} commands"))

    print("\n=== 9. SECRET SCAN (repo) ===")
    out = subprocess.run([sys.executable, "-m", "mindbot_pipeline.cli", "scan"],
                         cwd=FW, capture_output=True, text=True, env=_utf8_env())
    clean = "clean" in out.stdout
    R["facts"]["scan_clean"] = clean
    # pick the first non-empty line; the CLI pads with blanks, so [1] can be out of range
    detail = next((l.strip() for l in out.stdout.splitlines() if l.strip()), "")
    import re as _re
    detail = _re.sub(r"\x1b\[[0-9;]*m", "", detail)          # strip ANSI for a clean report
    R["facts"]["scan_files"] = int(m.group(1)) if (m := _re.search(r"(\d+) tracked", detail)) else 0
    check("no secrets in tracked files", lambda: (clean, detail))

    print("\n=== 10. DOCTOR ===")
    d = subprocess.run([sys.executable, "-m", "mindbot_pipeline.cli", "doctor"],
                       cwd=FW, capture_output=True, text=True, env=_utf8_env())

    def _doctor():
        """A missing API key is a SETUP notice, not a broken environment.

        CI deliberately provides no OPENROUTER_API_KEY — that is how the nightly run stays free.
        Failing the whole audit over it would mean the nightly job is red every night for a
        reason we chose on purpose, and a permanently-red build is one nobody reads. So: accept
        a non-zero doctor ONLY when every flagged line is about a missing key, and say so in the
        result rather than hiding it.
        """
        out = (d.stdout or "") + (d.stderr or "")
        if d.returncode == 0:
            lines = [l.strip() for l in out.strip().splitlines() if l.strip()]
            return True, lines[-1] if lines else "ok"
        # Only lines that BEGIN with ✗ are findings. doctor also prints a summary
        # ("1 issue(s) — fix the ✗ lines above") which mentions ✗ but is not itself a finding —
        # counting it made every flagged set look mixed, so this check failed on exactly the
        # case it was written to allow.
        flagged = [l.strip() for l in out.splitlines() if l.strip().startswith(("✗", "FAIL"))]
        keyish = [l for l in flagged
                  if "key" in l.lower() or "template mode" in l.lower() or "ollama" in l.lower()]
        if flagged and len(keyish) == len(flagged):
            return True, f"{len(flagged)} backend notice(s) — expected with no API key"
        return False, "; ".join(flagged)[:150] or f"exit {d.returncode}"

    check("environment healthy", _doctor)

    print(f"\n{'='*66}")
    print(f"  RESULT: {R['pass']} passed, {R['fail']} failed")
    print(f"{'='*66}")
    (FW / "_audit_facts.json").write_text(json.dumps(R, indent=2), encoding="utf-8")
    print(json.dumps(R["facts"], indent=1))
    return 0 if R["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
