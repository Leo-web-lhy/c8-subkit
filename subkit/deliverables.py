"""Deliverable matching for Eduseed-style challenges.

Real failure this module encodes (observed 2026-11-19, challenge C6):
the platform required pattern list "*app link*,*demo*,*repo link*,*AI log*"
reported missing even though README.md already contained every link.
Cause: the patterns are matched against FILE NAMES, not file contents.
Fix: name a real file after each pattern token. check() reports which
rule hit (basename vs full relative path) so the cause is never guessed.
"""
import fnmatch
import os
import unicodedata

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".scratch", ".venv"}


def split_patterns(spec):
    """Required-deliverables specs are comma separated strings, never arrays."""
    if isinstance(spec, (list, tuple)):
        raw = list(spec)
    else:
        raw = str(spec).replace("\uff0c", ",").split(",")
    return [p.strip() for p in raw if p.strip()]


def iter_files(root):
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name.endswith((".pyc", ".pyo")):
                continue
            full = os.path.join(base, name)
            yield os.path.relpath(full, root).replace("\\", "/")


def norm(text):
    return unicodedata.normalize("NFC", text).casefold()


def match_one(pattern, relpath):
    """Return 'basename' | 'path' | None for a single pattern/file pair."""
    pat = norm(pattern)
    base = norm(relpath.rsplit("/", 1)[-1])
    if fnmatch.fnmatchcase(base, pat):
        return "basename"
    if fnmatch.fnmatchcase(norm(relpath), pat):
        return "path"
    return None


def is_stub(path, min_chars=40):
    """A zero-byte or near-empty file satisfies a glob but delivers nothing."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return True
    if size == 0:
        return True
    if size > 2 * 1024 * 1024:
        return False
    try:
        with open(path, "rb") as fh:
            data = fh.read(2 * 1024 * 1024)
        text = data.decode("utf-8", "ignore")
    except OSError:
        return True
    return len("".join(text.split())) < min_chars


def check(root, spec):
    """Match every required pattern; report hits, misses and stub hits.

    Returns a dict so callers print facts instead of guessing:
      patterns  - parsed pattern list
      found     - pattern -> list of {path, rule}
      missing   - patterns with no file at all
      stubs     - pattern -> list of paths that matched but look empty
      ok        - True only when every pattern has at least one non-stub hit
    """
    root = os.path.abspath(root)
    files = list(iter_files(root))
    patterns = split_patterns(spec)
    found, missing, stubs = {}, [], {}
    for pattern in patterns:
        hits = []
        for rel in files:
            rule = match_one(pattern, rel)
            if rule:
                hits.append({"path": rel, "rule": rule})
        if not hits:
            missing.append(pattern)
            continue
        found[pattern] = hits
        bad = [h["path"] for h in hits if is_stub(os.path.join(root, h["path"].replace("/", os.sep)))]
        if bad:
            stubs[pattern] = bad
    ok = not missing and not stubs and bool(patterns)
    return {
        "root": root,
        "total_files": len(files),
        "patterns": patterns,
        "found": found,
        "missing": missing,
        "stubs": stubs,
        "ok": ok,
    }


def suggest_filename(pattern):
    """Turn a glob token into the smallest file name that will satisfy it."""
    token = pattern.replace("*", "").replace("?", "").strip()
    if not token:
        return "deliverable.md"
    if "." in token.rsplit("/", 1)[-1]:
        return token
    return token + ".md"


def ascii_ok(text):
    """Render text for the Windows console: keep ASCII, escape everything else.

    cli.emit() writes to stdout, and this machine kills any process that writes
    non-ASCII bytes to the console with 0xC0000005 before output is flushed.
    Non-ASCII therefore becomes \\uXXXX escapes rather than being dropped, so a
    Chinese file name still identifies itself in the log.
    """
    return str(text).encode("ascii", "backslashreplace").decode("ascii")
