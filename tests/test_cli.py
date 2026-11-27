"""Exercise the same command-line interface used by agents."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def run_cli(self, *args):
        env = dict(os.environ, PYTHONPATH=str(PROJECT / "src"))
        return subprocess.run(
            [sys.executable, "-m", "mie", *args],
            env=env, capture_output=True, text=True, encoding="utf-8",
        )

    def search(self, query, *args):
        result = self.run_cli("search", query, "--root", str(self.root), "--format", "json", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_returns_relevant_source_with_original_lines(self):
        self.write("auth.py", "# Authentication\ndef verify_session(token):\n    return token == 'demo'\n")
        self.write("unrelated.py", "print('hello')\n")
        result = self.search("verify_session")
        self.assertIn("2: def verify_session(token):", result["context"])
        self.assertEqual(result["snippets"][0]["path"], "auth.py")
        self.assertNotIn("unrelated.py", result["context"])

    def test_context_obeys_budget_and_reports_truncation(self):
        self.write("large.py", "needle = '" + "x" * 2000 + "'\n")
        result = self.search("needle", "--budget", "512")
        self.assertLessEqual(len(result["context"]), 512)
        self.assertEqual(result["context_chars"], len(result["context"]))
        self.assertTrue(result["truncated"])
        self.assertIn("[excerpt truncated]", result["context"])

    def test_skips_sensitive_generated_binary_and_oversized_files(self):
        for name in (".env", ".env.local", "private.key", ".aws/config", "node_modules/a.py", "secrets.json"):
            self.write(name, "needle PRIVATE")
        (self.root / "image.bin").write_bytes(b"needle\0PRIVATE")
        self.write("huge.txt", "needle" * 50000)
        self.write("safe.py", "needle = 'public'\n")
        result = self.search("needle")
        self.assertEqual([s["path"] for s in result["snippets"]], ["safe.py"])
        self.assertNotIn("PRIVATE", result["context"])

    def test_no_matches_is_success(self):
        self.write("app.py", "print('hello')\n")
        result = self.search("missing")
        self.assertEqual(result["context"], "")
        self.assertEqual(result["snippets"], [])

    def test_invalid_inputs_fail_cleanly(self):
        for args in (("search", "___"), ("search", "x", "--budget", "0"),
                     ("search", "x", "--root", str(self.root / "absent"))):
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)

    def test_unicode_source_is_preserved(self):
        self.write("café.py", "# pembayaran\nstatus = 'berhasil ✓'\n")
        result = self.search("pembayaran")
        self.assertIn("berhasil ✓", result["context"])
        self.assertEqual(result["snippets"][0]["path"], "café.py")

    def test_results_are_deterministic_and_windows_do_not_duplicate_lines(self):
        self.write("b.py", "needle = 1\nneedle = 2\n")
        self.write("a.py", "needle = 1\nneedle = 2\n")
        first = self.search("needle")
        self.assertEqual(first, self.search("needle"))
        self.assertEqual(first["snippets"][0]["path"], "a.py")
        self.assertEqual(first["context"].count("1: needle = 1"), 2)

    @unittest.skipUnless(shutil.which("git"), "Git is not installed")
    def test_gitignore_excludes_untracked_files_but_keeps_tracked_files(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        self.write(".gitignore", "ignored/\ntracked.py\n")
        self.write("ignored/no.py", "needle PRIVATE")
        self.write("tracked.py", "needle = 42")
        subprocess.run(["git", "-C", str(self.root), "add", "-f", "tracked.py"], check=True, capture_output=True)
        result = self.search("needle")
        self.assertEqual(result["listing"], "git")
        self.assertEqual([s["path"] for s in result["snippets"]], ["tracked.py"])

    def test_symlink_targets_are_not_read(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "private.txt"
            target.write_text("needle PRIVATE", encoding="utf-8")
            try:
                (self.root / "link.txt").symlink_to(target)
            except OSError:
                self.skipTest("Creating symlinks requires additional OS privileges")
            self.assertEqual(self.search("needle")["context"], "")

    def test_terminal_control_characters_are_escaped(self):
        self.write("a.py", "needle = '\x1b[31mred'\n")
        result = self.search("needle")
        self.assertNotIn("\x1b", result["context"])
        self.assertIn("\\u001b", result["context"])

    def test_truncation_keeps_match_after_long_context(self):
        self.write("a.py", "x" * 1000 + "\ndef needle(): pass\n")
        result = self.search("needle", "--budget", "512")
        self.assertIn("2: def needle(): pass", result["context"])
        self.assertLessEqual(len(result["context"]), 512)

    def test_truncation_keeps_match_at_end_of_long_line(self):
        self.write("a.py", "x" * 2000 + " needle\n")
        result = self.search("needle", "--budget", "512")
        self.assertIn("needle", result["context"])
        self.assertLessEqual(len(result["context"]), 512)

    def test_text_output_preserves_unicode_in_pipes_and_reports_scan(self):
        self.write("app.py", "needle = '✓'\n")
        env = dict(os.environ, PYTHONPATH=str(PROJECT / "src"), PYTHONIOENCODING="cp1252")
        result = subprocess.run(
            [sys.executable, "-m", "mie", "search", "needle", "--root", str(self.root)],
            env=env, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("✓", result.stdout.decode("utf-8"))
        self.assertIn("Scan: 1/1 files", result.stderr.decode("utf-8"))

    def test_clipping_accounts_for_expanding_unicode_casefold(self):
        self.write("a.py", "ß" * 1000 + "needle" + "x" * 1000 + "\n")
        result = self.search("needle", "--budget", "512")
        self.assertIn("needle", result["context"])
        self.assertLessEqual(len(result["context"]), 512)

    @unittest.skipUnless(shutil.which("git"), "Git is required by the benchmark")
    def test_benchmark_runs_from_a_relative_temporary_directory(self):
        env = dict(os.environ, TMPDIR=".", TEMP=".", TMP=".")
        result = subprocess.run([sys.executable, str(PROJECT / "benchmarks" / "run.py")],
                                cwd=self.root, env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["coverage"], "3/3")

    def test_search_resolves_relative_roots_for_benchmark_callers(self):
        self.write("app.py", "needle = 1\n")
        env = dict(os.environ, PYTHONPATH=str(PROJECT / "src"))
        result = subprocess.run(
            [sys.executable, "-c", "from pathlib import Path; from mie.cli import search; import json; print(json.dumps(search(Path('.'), 'needle')))"],
            cwd=self.root, env=env, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("needle = 1", json.loads(result.stdout)["context"])


if __name__ == "__main__":
    unittest.main()
