"""Regression tests for the CLI layer.

Both bugs below shipped in 0.1.0 and were found by running the documented
command, not by reading code:

  1. `python -m subkit` -- no __main__.py, so every documented invocation
     died instantly with "No module named subkit.__main__" and exit 1.
  2. `deliverables.ascii_ok` -- called 7 times from cli.py, never defined.
     It only fires once the MISSING branch is taken, so a workspace that
     happened to be complete never exposed it; `doctor` crashed every time.

Both are pure control-flow bugs, which is exactly what tests must pin down.
"""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from subkit import cli, deliverables


class AsciiOkTest(unittest.TestCase):
    def test_function_exists(self):
        # Bug 2: cli.py called it in 7 places while deliverables.py had no such name.
        self.assertTrue(hasattr(deliverables, "ascii_ok"))

    def test_escapes_non_ascii(self):
        self.assertEqual(deliverables.ascii_ok("*AI\u65e5\u5fd7*"), "*AI\\u65e5\\u5fd7*")

    def test_output_is_pure_ascii(self):
        out = deliverables.ascii_ok("\u63d0\u4ea4\u8eab\u4efd 2023108610260")
        out.encode("ascii")  # raises UnicodeEncodeError if the contract breaks
        self.assertIn("2023108610260", out)


class ModuleEntryPointTest(unittest.TestCase):
    def test_main_module_exists(self):
        # Bug 1: README/examples document `python -m subkit`; the package needs
        # a __main__ module for that form to work at all.
        import subkit.__main__ as entry
        self.assertTrue(callable(getattr(entry, "main", None)))

    def test_runs_as_module(self):
        # Known environment flake (measured, not guessed): on this Windows box
        # the bundled Python occasionally refuses to spawn a child interpreter
        # with PermissionError [WinError 5] -- roughly 1 run in 16, and never
        # under `-v`. The retry below wraps ONLY the spawn failure; a non-zero
        # exit or missing output still fails the test hard.
        import subprocess
        import time
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        last = None
        for attempt in range(3):
            try:
                proc = subprocess.run([sys.executable, "-m", "subkit", "--help"],
                                      cwd=root, capture_output=True, text=True)
                break
            except OSError as exc:  # PermissionError is an OSError subclass
                last = exc
                time.sleep(0.3 * (attempt + 1))
        else:
            self.fail("spawn failed 3x with %r" % (last,))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("preflight", proc.stdout)


class PreflightCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.detail = os.path.join(self.tmp, "detail.txt")

    def _run(self, workspace, required):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(["preflight", workspace, "--required", required,
                             "--detail", self.detail])
        out = buf.getvalue()
        out.encode("ascii")  # console contract: emit() must never leak non-ASCII
        return code, out

    def test_missing_pattern_exits_3_without_crashing(self):
        code, out = self._run(self.tmp, "*demo*")
        self.assertEqual(code, 3)
        self.assertIn("MISSING", out)
        self.assertIn("demo.md", out)
        self.assertIn("verdict=NOT_READY", out)

    def test_complete_workspace_exits_0(self):
        with open(os.path.join(self.tmp, "demo.md"), "w", encoding="utf-8") as fh:
            fh.write("x" * 100)
        code, out = self._run(self.tmp, "*demo*")
        self.assertEqual(code, 0)
        self.assertIn("verdict=READY", out)

    def test_stub_is_reported_not_passed(self):
        with open(os.path.join(self.tmp, "demo.md"), "w", encoding="utf-8") as fh:
            fh.write("\n")
        code, out = self._run(self.tmp, "*demo*")
        self.assertEqual(code, 3)
        self.assertIn("STUB", out)

    def test_detail_file_written_outside_workspace(self):
        self._run(self.tmp, "*demo*")
        with io.open(self.detail, "r", encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("[MISSING] *demo*", body)


class DoctorCliTest(unittest.TestCase):
    def test_doctor_crashes_on_ascii_ok(self):
        # Bug 2 surfaced here deterministically: doctor always formats values.
        buf = io.StringIO()
        with mock.patch.object(cli.rm, "is_public", return_value=(True, "public")):
            with redirect_stdout(buf):
                code = cli.main(["doctor"])
        out = buf.getvalue()
        out.encode("ascii")
        self.assertEqual(code, 0)
        self.assertIn("api_github", out)


if __name__ == "__main__":
    unittest.main()
