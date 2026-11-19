"""Byte-level verification of a published repository over the GitHub REST API.

Real constraints this module encodes (measured on this machine, 2026-11):
  * `git push` over github.com:443 times out, while api.github.com answers,
    so publishing and verifying both go through the REST API.
  * A recursive tree listing is enough for verification: a git blob id is
    derived from the exact bytes, so an equal id means an equal file.
  * An empty repository cannot be diffed; it has to be bootstrapped first.
"""
import json
import urllib.error
import urllib.request

API = "https://api.github.com"


class RemoteError(RuntimeError):
    pass


def _request(token, method, path, data=None, base=API, timeout=90):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "subkit",
    }
    if token:
        headers["Authorization"] = "token " + token
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except ValueError:
            payload = {"raw": raw[:300]}
        return exc.code, payload
    except urllib.error.URLError as exc:
        raise RemoteError("network unreachable: %s" % exc.reason)


def list_blobs(owner, repo, token, branch="main"):
    """Return {path: git_blob_sha} for every blob in the branch."""
    status, payload = _request(
        token, "GET", "/repos/%s/%s/git/trees/%s?recursive=1" % (owner, repo, branch)
    )
    if status == 404:
        raise RemoteError("repository or branch not found: %s/%s@%s" % (owner, repo, branch))
    if status != 200:
        raise RemoteError("tree listing failed: HTTP %s" % status)
    if payload.get("truncated"):
        raise RemoteError("tree listing truncated; narrow the branch before verifying")
    return {
        node["path"]: node["sha"]
        for node in payload.get("tree", [])
        if node.get("type") == "blob"
    }


def is_public(owner, repo):
    """Anonymous read: proves the repository is reachable without credentials."""
    status, payload = _request(None, "GET", "/repos/%s/%s" % (owner, repo))
    if status != 200:
        return False, "HTTP %s" % status
    if payload.get("private"):
        return False, "repository is private"
    return True, payload.get("html_url") or ""


def verify(owner, repo, manifest, token, branch="main"):
    """Compare a local manifest with the remote tree; no downloads needed."""
    from .manifest import SKIP_FILES, compare

    listing = list_blobs(owner, repo, token, branch)
    # A manifest cannot list itself (manifest.SKIP_FILES), so the manifest file
    # sitting on the remote is not part of the comparison universe. Excluding it
    # is correct; dropping it silently is not, because that would also hide a
    # stale manifest that was published and then edited by hand.
    ignored = sorted(p for p in listing if p.rsplit("/", 1)[-1] in SKIP_FILES)
    remote = {p: s for p, s in listing.items() if p not in ignored}
    matched, mismatched, missing, extra = compare(manifest, remote)
    public_ok, note = is_public(owner, repo)
    return {
        "matched": matched,
        "mismatched": mismatched,
        "missing_on_remote": missing,
        "extra_on_remote": extra,
        "ignored_on_remote": ignored,
        "public": public_ok,
        "public_note": note,
        "remote_file_count": len(remote),
        "ok": not mismatched and not missing and not extra and public_ok,
    }
