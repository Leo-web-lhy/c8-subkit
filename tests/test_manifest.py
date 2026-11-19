"""Regression tests for the byte manifest (failure class 2: CRLF false diff)."""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from subkit import manifest as mf

EMPTY_BLOB = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
HELLO_BLOB = "ce013625030ba8dba906f756967f9e9ca394464a"


class TestGitBlob(unittest.TestCase):
    def test_empty_blob_id_matches_git_hash_object(self):
        self.assertEqual(mf.git_blob_sha(b""), EMPTY_BLOB)

    def test_hello_blob_id_matches_git_hash_object(self):
        self.assertEqual(mf.git_blob_sha(b"hello\n"), HELLO_BLOB)

    def test_blob_id_is_not_the_plain_file_sha1(self):
        plain = hashlib.sha1(b"hello\n").hexdigest()
        self.assertNotEqual(mf.git_blob_sha(b"hello\n"), plain)

    def test_crlf_and_lf_have_different_blob_ids(self):
        """The 2026-11-19 false positive: same text, different bytes."""
        a = mf.git_blob_sha(b"line\n")
        b = mf.git_blob_sha(b"line\r\n")
        self.assertNotEqual(a, b)

    def test_sha1_file_matches_memory_hash(self):
        root = tempfile.mkdtemp()
        try:
            path = os.path.join(root, "a.txt")
            with open(path, "wb") as fh:
                fh.write(b"hello\n")
            self.assertEqual(mf.sha1_file(path), hashlib.sha1(b"hello\n").hexdigest())
        finally:
            shutil.rmtree(root, ignore_errors=True)


class TestBuild(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        with open(os.path.join(self.root, "a.txt"), "wb") as fh:
            fh.write(b"hello\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_build_records_both_hashes(self):
        data = mf.build(self.root)
        self.assertEqual(data["file_count"], 1)
        entry = data["files"][0]
        self.assertEqual(entry["path"], "a.txt")
        self.assertEqual(entry["bytes"], 6)
        self.assertEqual(entry["git_blob"], HELLO_BLOB)
        self.assertEqual(entry["sha1"], hashlib.sha1(b"hello\n").hexdigest())

    def test_manifest_does_not_describe_itself(self):
        mf.write(self.root, "manifest.json")
        data = mf.build(self.root)
        self.assertNotIn("manifest.json", [e["path"] for e in data["files"]])

    def test_write_then_load_roundtrip(self):
        path, data = mf.write(self.root, "m.json")
        again = mf.load(path)
        self.assertEqual(again["file_count"], data["file_count"])
        self.assertEqual(again["files"][0]["git_blob"], HELLO_BLOB)

    def test_manifest_is_utf8_json(self):
        path, _ = mf.write(self.root, "m.json")
        with open(path, "rb") as fh:
            raw = fh.read()
        self.assertIsInstance(json.loads(raw.decode("utf-8")), dict)


class TestCompare(unittest.TestCase):
    def test_identical_and_mismatched_and_missing_and_extra(self):
        local = {"files": [
            {"path": "same.md", "git_blob": "aaa"},
            {"path": "diff.md", "git_blob": "bbb"},
            {"path": "gone.md", "git_blob": "ccc"},
        ]}
        remote = {"same.md": "aaa", "diff.md": "zzz", "new.md": "ddd"}
        matched, mismatched, missing, extra = mf.compare(local, remote)
        self.assertEqual(matched, ["same.md"])
        self.assertEqual([m["path"] for m in mismatched], ["diff.md"])
        self.assertEqual(missing, ["gone.md"])
        self.assertEqual(extra, ["new.md"])

    def test_same_content_is_matched_not_guessed(self):
        local = {"files": [{"path": "a.md", "git_blob": HELLO_BLOB}]}
        matched, mismatched, missing, extra = mf.compare(local, {"a.md": HELLO_BLOB})
        self.assertEqual(matched, ["a.md"])
        self.assertEqual((mismatched, missing, extra), ([], [], []))


if __name__ == "__main__":
    unittest.main()
