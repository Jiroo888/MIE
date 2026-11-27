"""Reproducible synthetic retrieval benchmark. No network or model calls."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from mie.cli import search


def main():
    tasks = [
        ("verify_session", "auth.py", "def verify_session(token):"),
        ("calculate_total", "billing.py", "def calculate_total(items):"),
        ("retry_request", "network.py", "def retry_request(client):"),
    ]
    with tempfile.TemporaryDirectory(prefix="mie-benchmark-") as temporary:
        root = Path(temporary)
        # A real Git root makes file enumeration identical inside/outside a checkout.
        subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
        for _, filename, declaration in tasks:
            (root / filename).write_text(
                "# Synthetic example; not production business logic.\n" + declaration + "\n    return None\n",
                encoding="utf-8",
            )
        for n in range(40):
            (root / f"unrelated_{n:02}.py").write_text(
                "\n".join(f"setting_{i} = {i}  # unrelated configuration" for i in range(100)) + "\n",
                encoding="utf-8",
            )
        rows = []
        for query, expected_path, expected_line in tasks:
            started = time.perf_counter()
            result = search(root, query, budget=2000)
            elapsed = (time.perf_counter() - started) * 1000
            baseline = result["stats"]["scanned_chars"]
            covered = any(s["path"] == expected_path for s in result["snippets"]) and expected_line in result["context"]
            rows.append({
                "query": query, "expected_path": expected_path, "covered": covered,
                "baseline_chars": baseline, "context_chars": result["context_chars"],
                "reduction_percent": round(100 * (1 - result["context_chars"] / baseline), 2),
                "elapsed_ms": round(elapsed, 2),
            })
        report = {
            "benchmark": "synthetic literal-symbol lookup", "files": 43, "budget_chars": 2000,
            "coverage": f"{sum(row['covered'] for row in rows)}/{len(rows)}",
            "baseline": "Decoded characters in all scanned eligible files, excluding line headers.",
            "limitations": "Easy synthetic fixture. No agent execution, tokenizer counts, API costs, or real-world accuracy evaluation.",
            "tasks": rows,
        }
        print(json.dumps(report, indent=2))
        return 0 if all(row["covered"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
