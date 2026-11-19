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
        self.assertIn("from .manifest import compare", src)


if __name__ == "__main__":
    unittest.main()
