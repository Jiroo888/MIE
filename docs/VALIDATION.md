# Local validation

Validated on Windows with Python 3.14.7 on November 27, 2026.

| Check | Result |
| --- | --- |
| Build and install in an isolated virtual environment | Passed |
| Installed `mie --version` command | `0.1.0` |
| CLI integration suite | 13 passed, 1 skipped |
| UTF-8 output through CP1252-configured pipes | Passed |
| Budget clipping retains matches after long context, within long lines, and after expanding Unicode casefold characters | Passed |
| Synthetic retrieval benchmark | 3/3 labeled targets present |

The skipped test requires permission to create symlinks. File exclusions, Git-aware selection, JSON output, deterministic retrieval, invalid input handling, terminal-control escaping, and original line references are covered by the CLI suite.

The synthetic benchmark returned 125–129 context characters from 175,495 eligible source characters. This deliberately easy fixture measures retrieval coverage and output size, not agent correctness, actual tokenizer counts, or API spending. Run `python benchmarks/run.py` to reproduce it; timings will vary.

Review found and corrected Windows output encoding, match loss during clipping, missing text-mode scan statistics, and an unsupported benchmark wording claim. The README now distinguishes integration-test coverage from benchmark coverage.

Linux and Python 3.11 were not run locally. The included GitHub Actions matrix is configured for Windows/Linux and Python 3.11/3.14; a passing hosted run must be verified after publication.
