# Night shift — 2026-08-12 08:16 UTC

**NEEDS A LOOK** — 0/12 platform × version combinations passed the full audit.

[Full run log](https://github.com/TheMindExpansionNetwork/mindbot-framework/actions/runs/31577518008)

| Platform | Python | Result | Tests | Actions | Notes |
|---|---|---|--:|--:|---|
| macos-latest | 3.10 | **FAIL** | 190 | 25 | 2 check(s) failed |
| macos-latest | 3.11 | **FAIL** | 190 | 25 | 2 check(s) failed |
| macos-latest | 3.12 | **FAIL** | 190 | 25 | 2 check(s) failed |
| macos-latest | 3.13 | **FAIL** | 190 | 25 | 2 check(s) failed |
| ubuntu-latest | 3.10 | **FAIL** | 190 | 25 | 2 check(s) failed |
| ubuntu-latest | 3.11 | **FAIL** | 190 | 25 | 2 check(s) failed |
| ubuntu-latest | 3.12 | **FAIL** | 190 | 25 | 2 check(s) failed |
| ubuntu-latest | 3.13 | **FAIL** | 190 | 25 | 2 check(s) failed |
| windows-latest | 3.10 | **FAIL** | 190 | 25 | 2 check(s) failed |
| windows-latest | 3.11 | **FAIL** | 190 | 25 | 2 check(s) failed |
| windows-latest | 3.12 | **FAIL** | 190 | 25 | 2 check(s) failed |
| windows-latest | 3.13 | **FAIL** | 190 | 25 | 2 check(s) failed |

## What this run does not establish

- **No live model calls.** No API key is present in CI, so every model path ran in template
  mode. This validates the machinery around the models, not the models.
- **Not a security audit.** No dependency CVE scan, no fuzzing, no third-party review.
- **Fresh checkout each run.** The ledger starts near-empty, so this exercises chain
  *mechanics*, not the long-lived history in the committed ledger.

<sub>Written by `framework/_nightly_report.py`. Every number above came from a job that ran;
nothing here is asserted by hand.</sub>
