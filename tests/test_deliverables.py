"""Regression tests for deliverable matching (failure class 1: glob vs content)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from subkit import deliverables as dv


TEXT = "x" * 200


class TestPatterns(unittest.TestCase):
    def test_comma_string_is_the_real_format(self):
        self.assertEqual(dv.split_patterns("*a*,*b*"), ["*a*", "*b*"])

    def test_chinese_comma_is_normalised(self):
        spec = "*app*\uff0c*repo*"
        self.assertEqual(dv.split_patterns(spec), ["*app*", "*repo*"])

    def test_blank_tokens_dropped(self):
        self.assertEqual(dv.split_patterns("*a*, ,*b*,"), ["*a*", "*b*"])


class TestMatchRules(unittest.TestCase):
    def test_basename_match_reports_basename(self):
        self.assertEqual(dv.match_one("*AI*", "docs/AI_log.md"), "basename")

    def test_directory_pattern_reports_path(self):
        self.assertEqual(dv.match_one("docs/*", "docs/a.md"), "path")

    def test_no_match(self):
        self.assertIsNone(dv.match_one("*demo*", "README.md"))

    def test_case_insensitive(self):
        self.assertEqual(dv.match_one("*ai*", "AI.md"), "basename")


class TestCheck(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def _put(self, rel, content=TEXT):
        full = os.path.join(self.root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True) if os.path.dirname(full) else None
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)

    def test_link_in_readme_does_not_satisfy_a_pattern(self):
        """The C6 failure: the link was in README, the name had to exist."""
        self._put("README.md", "see https://example.com app and repo\n" * 5)
        res = dv.check(self.root, "*app link*,*repo link*")
        self.assertFalse(res["ok"])
        self.assertEqual(sorted(res["missing"]), ["*app link*", "*repo link*"])

    def test_named_pointer_files_satisfy(self):
        self._put("app link.md")
        self._put("repo link.md")
        res = dv.check(self.root, "*app link*,*repo link*")
        self.assertTrue(res["ok"])
        self.assertEqual(res["found"]["*app link*"][0]["rule"], "basename")

    def test_empty_file_is_a_stub_not_a_pass(self):
        self._put("AI log.md", "")
        res = dv.check(self.root, "*AI log*")
        self.assertFalse(res["ok"])
        self.assertIn("*AI log*", res["stubs"])
        self.assertEqual(res["missing"], [])

    def test_short_file_is_a_stub(self):
        self._put("demo.md", "todo")
        res = dv.check(self.root, "*demo*")
        self.assertFalse(res["ok"])

    def test_git_dir_is_skipped(self):
        self._put(".git/config")
        res = dv.check(self.root, "*")
        self.assertEqual(res["total_files"], 0)

    def test_suggest_filename(self):
        self.assertEqual(dv.suggest_filename("*AI log*"), "AI log.md")
        self.assertEqual(dv.suggest_filename("*proposal*"), "proposal.md")


if __name__ == "__main__":
    unittest.main()
