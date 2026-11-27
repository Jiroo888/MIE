# Retrieval benchmark

Run from the repository root:

```sh
python benchmarks/run.py
```

Python 3.11+ and Git are required. The script creates and cleans a temporary Git repository. It makes no model or network calls and leaves the source repository unchanged.

The fixture has three labeled functions plus 40 unrelated Python files, each with 100 configuration lines. Each query names one function. The context budget is 2,000 characters per query.

The baseline is decoded text in all scanned eligible files, without excerpt headers. Selected context includes excerpt headers and line numbering. Reduction is `100 × (1 - context_chars / baseline_chars)`. Coverage requires both the expected filename and its declaration to appear in the result. The script exits nonzero if any labeled target is absent.

This tests straightforward literal lookup and output reduction. It does not test dependency tracing, ambiguous natural language, multi-file bug fixes, or correctness after edits. Larger realistic fixtures and agent task evaluations are required before making general efficiency claims. Timing is informational, not a pass/fail threshold.
