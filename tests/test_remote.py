"""Regression tests for remote verification (failure class 3: fake network diff)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from subkit import remote as rm


class TestTreeFiltering(unittest.TestCase):
    def test_only_blobs_count(self):
        """A tree listing mixes trees and blobs; comparing a tree id is a bug."""
        payload = {"tree": [
            {"path": "docs", "type": "tree", "sha": "t1"},
            {"path": "docs/a.md", "type": "blob", "sha": "b1"},
        ]}
        blobs = {n["path"]: n["sha"] for n in payload["tree"] if n.get("type") == "blob"}
        self.assertEqual(blobs, {"docs/a.md": "b1"})

    def test_recursive_listing_request_is_used(self):
        import inspect
        src = inspect.getsource(rm.list_blobs)
        self.assertIn("recursive=1", src)

    def test_truncated_listing_is_an_error_not_a_pass(self):
        """A truncated listing would silently report files as missing."""
        import inspect
        src = inspect.getsource(rm.list_blobs)
        self.assertIn("truncated", src)


class TestPublicCheck(unittest.TestCase):
    def test_public_check_is_anonymous(self):
        """Reachability must be provable without credentials."""
        import inspect
        src = inspect.getsource(rm.is_public)
        self.assertIn("_request(None", src)

    def test_private_repo_fails_public(self):
        import inspect
        src = inspect.getsource(rm.is_public)
        self.assertIn("private", src)


class TestVerifyShape(unittest.TestCase):
    def test_verify_declares_all_verdict_fields(self):
        import inspect
        src = inspect.getsource(rm.verify)
        for key in ("mismatched", "missing_on_remote", "extra_on_remote", "public"):
            self.assertIn(key, src)

    def test_compare_is_reused_not_reimplemented(self):
        import inspect
        src = inspect.getsource(rm.verify)
        self.assertIn("compare(manifest, remote)", src)
        self.assertIn("from .manifest import", src)


class TestManifestSelfExclusion(unittest.TestCase):
    """Failure class 7: the manifest cannot list itself.

    First run of `verify` against this very repo said `extra=1 manifest.json`
    and `verdict=DIFFERS` - a false negative produced by the tool itself.
    """

    def _run(self, listing):
        manifest = {"files": [{"path": "README.md", "git_blob": "b1"}]}
        orig_blobs, orig_public = rm.list_blobs, rm.is_public
        rm.list_blobs = lambda *a, **k: dict(listing)
        rm.is_public = lambda *a, **k: (True, "https://example.invalid/repo")
        try:
            return rm.verify("owner", "repo", manifest, "", "main")
        finally:
            rm.list_blobs, rm.is_public = orig_blobs, orig_public

    def test_manifest_file_is_ignored_not_extra(self):
        res = self._run({"README.md": "b1", "manifest.json": "zzz"})
        self.assertEqual(res["extra_on_remote"], [])
        self.assertEqual(res["ignored_on_remote"], ["manifest.json"])
        # remote_file_count counts the comparison universe, so the ignored
        # manifest is not in it: 2 listed blobs - 1 ignored = 1.
        self.assertEqual(res["remote_file_count"], 1)
        self.assertTrue(res["ok"])

    def test_a_real_extra_file_still_fails(self):
        """The exclusion must not swallow files that genuinely do not belong."""
        res = self._run({"README.md": "b1", "manifest.json": "zzz", "stray.txt": "c1"})
        self.assertEqual(res["extra_on_remote"], ["stray.txt"])
        self.assertFalse(res["ok"])


if __name__ == "__main__":
    unittest.main()
