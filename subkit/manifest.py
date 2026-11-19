"""Byte-level manifest of a delivery workspace.

Why sha1 of raw bytes and not `git status`:
on 2026-11-19 git reported five modified files in a clean tree; the cause was
CRLF/LF normalisation, not real edits. Byte hashes never lie about that.
"""
import hashlib
import io
import json
import os
import time

from .deliverables import iter_files

SKIP_FILES = {"manifest.json"}


def git_blob_sha(data):
    """Git object id of a blob: sha1(b"blob <len>\\0" + content).

    A tree listing returns this id, not a plain file sha1. Comparing the two
    directly produces a fake mismatch on every file, so both are stored and
    each comparison uses the matching one.
    """
    h = hashlib.sha1()
    h.update(("blob %d\0" % len(data)).encode("ascii"))
    h.update(data)
    return h.hexdigest()


def sha1_file(path, chunk=1 << 20):
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def build(root):
    root = os.path.abspath(root)
    entries = []
    for rel in iter_files(root):
        if rel.rsplit("/", 1)[-1] in SKIP_FILES:
            continue
        full = os.path.join(root, rel.replace("/", os.sep))
        with open(full, "rb") as fh:
            data = fh.read()
        entries.append({
            "path": rel,
            "bytes": len(data),
            "sha1": hashlib.sha1(data).hexdigest(),
            "git_blob": git_blob_sha(data),
        })
    return {
        "root": root,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "file_count": len(entries),
        "total_bytes": sum(e["bytes"] for e in entries),
        "files": entries,
    }


def write(root, out_name="manifest.json"):
    data = build(root)
    path = os.path.join(root, out_name)
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(data, ensure_ascii=False, indent=2))
        fh.write("\n")
    return path, data


def load(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def compare(local_manifest, remote_map):
    """remote_map: path -> git blob sha of the remote file.

    Returns (matched, mismatched, missing_on_remote, extra_on_remote).
    A path present on both sides with different bytes is `mismatched`,
    never silently equal: that is the CRLF false-positive guard.
    """
    local = {e["path"]: e["git_blob"] for e in local_manifest["files"]}
    matched, mismatched = [], []
    for path, sha in sorted(local.items()):
        if path not in remote_map:
            continue
        if remote_map[path] == sha:
            matched.append(path)
        else:
            mismatched.append({"path": path, "local": sha, "remote": remote_map[path]})
    missing = sorted(p for p in local if p not in remote_map)
    extra = sorted(p for p in remote_map if p not in local)
    return matched, mismatched, missing, extra
