import io, os, re
p = os.path.join("subkit", "manifest.py")
s = io.open(p, "r", encoding="utf-8").read()

s = s.replace(
'''def sha1_file(path, chunk=1 << 20):''',
'''def git_blob_sha(data):
    """Git object id of a blob: sha1(b"blob <len>\\\\0" + content).

    Tree listing returns this id, not a plain file sha1. Comparing the two
    directly would produce a fake mismatch on every file; keep them separate.
    """
    h = hashlib.sha1()
    h.update(("blob %d\\0" % len(data)).encode("ascii"))
    h.update(data)
    return h.hexdigest()


def sha1_file(path, chunk=1 << 20):''')

s = s.replace(
'''def build(root):
    root = os.path.abspath(root)
    entries = []
    for rel in iter_files(root):
        if rel.rsplit("/", 1)[-1] in SKIP_FILES:
            continue
        full = os.path.join(root, rel.replace("/", os.sep))
        entries.append({
            "path": rel,
            "bytes": os.path.getsize(full),
            "sha1": sha1_file(full),
        })''',
'''def build(root):
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
            "sha1": sha1_file(full),
            "git_blob": git_blob_sha(data),
        })''')

s = s.replace(
'''    local = {e["path"]: e["sha1"] for e in local_manifest["files"]}''',
'''    local = {e["path"]: e["git_blob"] for e in local_manifest["files"]}''')

io.open(p, "w", encoding="utf-8", newline="\\n").write(s)
print("PATCHED len=%d" % len(s))
