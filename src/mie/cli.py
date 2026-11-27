"""Bounded, deterministic retrieval through a small CLI interface."""

import argparse
import fnmatch
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

from . import __version__


SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", ".venv", "venv",
    "__pycache__", "dist", "build", "coverage", ".next", ".cache",
    ".aws", ".ssh", ".azure", ".terraform",
}
SKIP_FILES = (
    ".env*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*",
    ".npmrc", ".pypirc", "credentials*", "secrets.*", "*.lock",
    "package-lock.json", "*.min.js", "*.map", "*.pyc",
)
MAX_FILE_BYTES = 256 * 1024
MAX_SCAN_BYTES = 32 * 1024 * 1024
MAX_FILES = 10000
MAX_CANDIDATES = 2000


def _redirected(path):
    if path.is_symlink():
        return True
    # Python 3.11 lacks Path.is_junction; Windows exposes the reparse attribute.
    return bool(getattr(path.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _excluded(relative):
    return (
        any(part.lower() in SKIP_DIRS for part in relative.parts[:-1])
        or any(fnmatch.fnmatchcase(relative.name.lower(), pattern) for pattern in SKIP_FILES)
    )


def _paths(root, warnings):
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],
            capture_output=True, timeout=15,
        )
        if result.returncode == 0:
            names = sorted(set(os.fsdecode(p) for p in result.stdout.split(b"\0") if p))
            if len(names) > MAX_FILES:
                warnings.append(f"File limit reached ({MAX_FILES}); search is incomplete.")
            return [Path(name) for name in names[:MAX_FILES]], "git"
    except (OSError, subprocess.TimeoutExpired):
        pass
    warnings.append("Using filesystem walk; .gitignore rules are not interpreted outside Git.")
    names = []

    def walk_error(error):
        warnings.append(f"Could not enumerate a directory ({type(error).__name__}).")

    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        dirs[:] = sorted(
            d for d in dirs if d.lower() not in SKIP_DIRS
            and not _redirected(Path(directory) / d)
        )
        for name in sorted(files):
            if len(names) >= MAX_FILES:
                warnings.append(f"File limit reached ({MAX_FILES}); search is incomplete.")
                return names, "walk"
            names.append((Path(directory) / name).relative_to(root))
    return names, "walk"


def _safe_file(root, relative):
    if relative.is_absolute() or ".." in relative.parts or _excluded(relative):
        return False
    current = root
    for part in relative.parts:
        current = current / part
        # Junctions on Windows also redirect reads outside the chosen source tree.
        if _redirected(current):
            return False
    return current.is_file() and current.resolve().is_relative_to(root)


def _display(value):
    # Escape terminal control characters from untrusted filenames and code.
    return "".join(c if c.isprintable() or c == "\t" else f"\\u{ord(c):04x}" for c in value)


def search(root, query, budget=12000, radius=3):
    """Select literal-term excerpts; budget applies to the context string only."""
    terms = sorted(set(re.findall(r"[^\W_]+", query.casefold(), re.UNICODE)))
    if not terms:
        raise ValueError("Query must contain at least one letter or number.")
    warnings = []
    paths, listing = _paths(root, warnings)
    candidates = []
    stats = {"listed_files": len(paths), "scanned_files": 0, "scanned_bytes": 0,
             "scanned_chars": 0, "skipped_files": 0}
    stop = False
    for relative in paths:
        try:
            if not _safe_file(root, relative):
                stats["skipped_files"] += 1
                continue
            path = root / relative
            if path.stat().st_size > MAX_FILE_BYTES:
                stats["skipped_files"] += 1
                continue
            if stats["scanned_bytes"] + MAX_FILE_BYTES + 1 > MAX_SCAN_BYTES:
                warnings.append("Scan byte limit reached; search is incomplete.")
                break
            with path.open("rb") as source:
                raw = source.read(MAX_FILE_BYTES + 1)
            stats["scanned_bytes"] += len(raw)
            if len(raw) > MAX_FILE_BYTES or b"\0" in raw:
                stats["skipped_files"] += 1
                continue
            text = raw.decode("utf-8-sig")
        except (OSError, UnicodeError):
            stats["skipped_files"] += 1
            continue
        stats["scanned_files"] += 1
        stats["scanned_chars"] += len(text)
        lines = text.splitlines()
        hits = []
        for index, line in enumerate(lines):
            score = sum(term in line.casefold() for term in terms)
            if score:
                hits.append((index, score))
        windows = []
        for index, score in hits:
            start, end = max(0, index - radius), min(len(lines), index + radius + 1)
            if windows and start <= windows[-1][1]:
                previous = windows[-1]
                windows[-1] = (previous[0], max(end, previous[1]), previous[2] + score)
            else:
                windows.append((start, end, score))
        for start, end, score in windows:
            focus = max((hit for hit in hits if start <= hit[0] < end), key=lambda hit: (hit[1], -hit[0]))[0]
            candidates.append({
                "path": relative.as_posix(), "start_line": start + 1, "end_line": end,
                "score": score, "lines": lines[start:end], "focus_line": focus + 1,
                "focus_text": lines[focus],
            })
            if len(candidates) >= MAX_CANDIDATES:
                warnings.append("Candidate limit reached; search is incomplete.")
                stop = True
                break
        if stop:
            break
    candidates.sort(key=lambda c: (-c["score"], c["path"], c["start_line"]))
    selected = []
    blocks = []
    used = 0
    truncated = False
    for candidate in candidates:
        header = f"--- {json.dumps(candidate['path'], ensure_ascii=True)}:{candidate['start_line']}-{candidate['end_line']} ---\n"
        body = "\n".join(f"{n}: {_display(line)}" for n, line in enumerate(candidate["lines"], candidate["start_line"]))
        block = header + body
        separator = "\n\n" if blocks else ""
        available = budget - used - len(separator)
        clipped = len(block) > available
        if clipped:
            marker = "\n[excerpt truncated]"
            if available < len(header) + len(marker) + 16:
                truncated = True
                continue
            prefix = f"{candidate['focus_line']}: "
            line = _display(candidate["focus_text"])
            room = available - len(header) - len(marker) - len(prefix)
            if len(line) > room:
                positions = [line.casefold().find(term) for term in terms if term in line.casefold()]
                folded_position = min(positions)
                folded_offset = 0
                position = 0
                # Casefold can expand characters (for example ß -> ss).
                for position, character in enumerate(line):
                    folded_offset += len(character.casefold())
                    if folded_offset > folded_position:
                        break
                start = max(0, min(position - room // 4, len(line) - room + 6))
                line = ("..." if start else "") + line[start:start + room - 6] + "..."
            block = header + prefix + line + marker
        blocks.append(separator + block)
        used += len(separator) + len(block)
        selected.append({k: candidate[k] for k in ("path", "start_line", "end_line", "score")} | {"truncated": clipped})
        truncated |= clipped
    context = "".join(blocks)
    return {
        "version": __version__, "query": query, "listing": listing,
        "context": context, "snippets": selected, "budget_chars": budget,
        "context_chars": len(context), "estimated_context_tokens": math.ceil(len(context) / 4),
        "token_estimate_method": "ceil(characters / 4); not a tokenizer count or token limit",
        "candidate_count": len(candidates), "truncated": truncated,
        "stats": stats, "warnings": warnings,
    }


def _bounded_int(low, high):
    def parse(value):
        try:
            number = int(value)
        except ValueError as error:
            raise argparse.ArgumentTypeError("Expected an integer.") from error
        if not low <= number <= high:
            raise argparse.ArgumentTypeError(f"Must be between {low} and {high}.")
        return number
    return parse


def main(argv=None):
    # Agent pipes and Windows redirection must preserve UTF-8 source text.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Local, budgeted source excerpts for coding agents.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("search", help="Find literal query terms in source files.")
    command.add_argument("query")
    command.add_argument("--root", type=Path, default=Path("."))
    command.add_argument("--budget", type=_bounded_int(512, 1000000), default=12000, metavar="CHARS")
    command.add_argument("--radius", type=_bounded_int(0, 30), default=3, metavar="LINES")
    command.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("Root must be a directory.")
        result = search(root, args.query, args.budget, args.radius)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        print(result["context"] or "No matching source excerpts.")
        print(f"Context: {result['context_chars']}/{args.budget} chars; "
              f"~{result['estimated_context_tokens']} tokens (estimate); "
              f"{len(result['snippets'])} excerpts.", file=sys.stderr)
        stats = result["stats"]
        print(f"Scan: {stats['scanned_files']}/{stats['listed_files']} files; "
              f"{stats['skipped_files']} skipped; {stats['scanned_bytes']} bytes read.", file=sys.stderr)
        for warning in result["warnings"]:
            print(f"Warning: {warning}", file=sys.stderr)
        if result["truncated"]:
            print("Warning: excerpts were omitted or truncated by the budget.", file=sys.stderr)
    return 0
