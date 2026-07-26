"""CONCURRENCY — the hash chain must survive multiple PROCESSES, not just threads.

WHY THIS TEST EXISTS (a real bug, measured):
  The ledger originally used only a threading lock. That is scoped to one process — but the real
  deployment runs `mindbot pulse` from cron WHILE a human runs commands. Three concurrent
  writers produced 17 duplicate seq numbers, lost 3 entries, and broke the chain at seq 2. A
  verifier reports that as tampering, so the entire proof story collapsed under normal use.

  The fix is an OS-level cross-process file lock around read-head -> append -> write-head.
  This test spawns REAL subprocesses; a threading lock cannot pass it.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FRAMEWORK = Path(__file__).resolve().parents[1]

WRITER = '''
import sys
from pathlib import Path
sys.path.insert(0, r"{fw}")
from mindbot_pipeline import collaboration as C
C.LEDGER_PATH = Path(r"{ledger}")
C.COLLAB = Path(r"{tmp}")
for i in range({n}):
    C.ledger("race", "proc-{tag} entry %d" % i, "probe")
'''


def _verify(entries: list[dict]) -> tuple[bool, str]:
    """Same rules as provenance.verify(), inlined so this test stands alone."""
    for i, e in enumerate(entries):
        blob = f"{e['seq']}|{e['ts']}|{e['agent']}|{e['event']}|{e['detail']}|{e['prev']}"
        if hashlib.sha256(blob.encode("utf-8")).hexdigest() != e["hash"]:
            return False, f"hash mismatch at seq {e['seq']}"
        if i > 0 and e["prev"] != entries[i - 1]["hash"]:
            return False, f"broken link at seq {e['seq']}"
    return True, "intact"


class TestCrossProcessLedger(unittest.TestCase):
    def _run(self, writers: int, per_writer: int):
        tmp = Path(tempfile.mkdtemp())
        ledger = tmp / "ledger.jsonl"
        procs = []
        for tag in [chr(65 + i) for i in range(writers)]:
            src = WRITER.format(fw=FRAMEWORK, ledger=ledger, tmp=tmp, tag=tag, n=per_writer)
            f = tmp / f"w{tag}.py"
            f.write_text(src, encoding="utf-8")
            procs.append(subprocess.Popen([sys.executable, str(f)],
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for p in procs:
            self.assertEqual(p.wait(timeout=180), 0, "a writer process failed")

        entries, corrupt = [], 0
        for ln in ledger.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                entries.append(json.loads(ln))
            except json.JSONDecodeError:
                corrupt += 1
        return entries, corrupt

    def test_three_processes_cannot_fork_the_chain(self):
        entries, corrupt = self._run(3, 20)
        self.assertEqual(corrupt, 0, "interleaved writes produced unparseable lines")
        self.assertEqual(len(entries), 60, "entries were LOST to a race")
        seqs = [e["seq"] for e in entries]
        self.assertEqual(len(seqs), len(set(seqs)), "DUPLICATE seq numbers — the chain forked")
        self.assertEqual(sorted(seqs), list(range(1, 61)), "sequence is not contiguous")
        ok, why = _verify(entries)
        self.assertTrue(ok, f"chain broken under concurrency: {why}")

    def test_six_processes_still_hold(self):
        entries, corrupt = self._run(6, 15)
        self.assertEqual(corrupt, 0)
        self.assertEqual(len(entries), 90)
        self.assertEqual(len({e["seq"] for e in entries}), 90)
        ok, why = _verify(entries)
        self.assertTrue(ok, f"chain broken at higher concurrency: {why}")


if __name__ == "__main__":
    unittest.main()
