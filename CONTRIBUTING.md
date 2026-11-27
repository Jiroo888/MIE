# Contributing to MIE

Thank you for helping improve Make It Efficient. MIE is an early prototype with a deliberately small scope: reliable, bounded source retrieval for coding agents.

## Set up a development environment

Create a virtual environment using Python 3.11 or later, activate it using your shell's standard command, and install the project:

```sh
python -m venv .venv
python -m pip install -e .
```

Run the installation command after activating `.venv`. Git is required for the benchmark.

## Validate a change

```sh
python -m unittest discover -s tests -v
python benchmarks/run.py
git diff --check
```

Tests exercise the CLI's observable behavior. Add a small regression fixture when changing ranking, truncation, file selection, or output encoding. Keep expected results independent of the implementation. Avoid tests that only repeat its formulas.

## Open an issue or pull request

Explain the problem, the command that reproduces it, and the expected result. Include a minimal, non-sensitive fixture when possible. For performance changes, describe the corpus, environment, quality checks, and comparison baseline.

Keep changes focused. Preserve the character-budget contract, source references, explicit warnings, and local-only retrieval. New runtime dependencies or changes to the JSON contract need a clear justification and documentation.

Do not upload credentials, proprietary source, or private agent transcripts. Redact sensitive information from examples and logs before sharing.
