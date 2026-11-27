# Changelog

## 0.1.0 — Initial prototype

- Local literal-term source retrieval through the `mie` command.
- Character-budgeted excerpts with original file paths and line windows.
- Matching-line prioritization when surrounding context exceeds the budget.
- UTF-8 text output and structured JSON with scan statistics and warnings.
- Git-aware enumeration, bounded reads, common sensitive-path exclusions, and symlink/reparse-point rejection.
- Companion agent skill, synthetic retrieval benchmark, and Windows/Linux CI configuration.

This release does not include MCP integration, semantic retrieval, model routing, or automatic tool interception.
