# MIE v0.1

Build a local, dependency-free Python CLI for coding agents. Given a repository and a text query, return relevant source excerpts with original line references within a character budget. No LLM, credentials, network calls, or source edits.

The CLI must support readable text and structured JSON, use Git's tracked and untracked non-ignored file list when available, skip common generated and sensitive paths, reject symlinks, and bound scanning. Outside Git, walk files with built-in exclusions; do not claim full gitignore support there.

Rank literal query terms deterministically. Context must fit its declared character budget including excerpt headers. Report selection and scan statistics, truncation, warnings, and approximate tokens explicitly. Token counts are estimates, not tokenizer guarantees. No matches is a valid result.

Ship an agent skill, professional English documentation and usage examples, MIT license, cross-platform CI, CLI integration tests, and a reproducible retrieval benchmark. Benchmark reports context reduction and retrieval coverage on labeled fixtures; it must not claim proven agent quality, dollar savings, or general performance.

The project is named MIE (Make It Efficient), with Python package and CLI named `mie`. Initial scope excludes MCP, model routing, semantic embeddings, caching, and automatic tool interception. Prepare a new GitHub repository under the user's connected account.
