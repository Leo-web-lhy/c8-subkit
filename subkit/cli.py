"""Command line entry point: python -m subkit <command> ...

Console discipline (hard-won on this machine):
writing non-ASCII text to the Windows console here kills the process with
0xC0000005 before any output file is written. Every console line therefore
goes through emit(), which keeps output ASCII; the full UTF-8 detail goes to
a log file that the caller can open afterwards.
"""
import argparse
import io
import json
import os
import sys
import time

from . import deliverables, manifest as mf, platform as pf, remote as rm


def emit(text=""):
    """Write one ASCII-safe line to stdout."""
    line = str(text).encode("ascii", "backslashreplace").decode("ascii")
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


class Detail:
    """UTF-8 detail sink; console only ever sees counts and verdicts."""

    def __init__(self, path):
        self.path = path
        self.fh = io.open(path, "w", encoding="utf-8")

    def add(self, text):
        self.fh.write(str(text) + "\n")
        self.fh.flush()

    def close(self):
        self.fh.close()


def cmd_preflight(args):
    detail = Detail(args.detail)
    result = deliverables.check(args.workspace, args.required)
    detail.add("root=%s" % result["root"])
    detail.add("total_files=%d" % result["total_files"])
    for pattern in result["patterns"]:
        hits = result["found"].get(pattern, [])
        if hits:
            detail.add("[FOUND] %s" % pattern)
            for hit in hits:
                detail.add("    %s  rule=%s" % (hit["path"], hit["rule"]))
        else:
            detail.add("[MISSING] %s  -> create a file named: %s"
                       % (pattern, deliverables.suggest_filename(pattern)))
    for pattern, paths in result["stubs"].items():
        detail.add("[STUB] %s  %s" % (pattern, ", ".join(paths)))
    detail.close()

    emit("preflight root=%s files=%d" % (result["root"], result["total_files"]))
    emit("patterns=%d found=%d missing=%d stubs=%d"
         % (len(result["patterns"]), len(result["found"]),
            len(result["missing"]), len(result["stubs"])))
    for pattern in result["missing"]:
        emit("  MISSING %s -> %s" % (deliverables.ascii_ok(pattern),
                                     deliverables.ascii_ok(deliverables.suggest_filename(pattern))))
    for pattern, paths in result["stubs"].items():
        emit("  STUB %s x%d" % (deliverables.ascii_ok(pattern), len(paths)))
    emit("verdict=%s" % ("READY" if result["ok"] else "NOT_READY"))
    emit("detail=%s" % args.detail)
    return 0 if result["ok"] else 3


def cmd_manifest(args):
    path, data = mf.write(args.workspace, args.out)
    emit("manifest written files=%d bytes=%d" % (data["file_count"], data["total_bytes"]))
    emit("path=%s" % path)
    return 0


def cmd_verify(args):
    data = mf.load(args.manifest)
    token = os.environ.get(args.token_env, "")
    if not token and args.token_file:
        with io.open(args.token_file, "r", encoding="utf-8") as fh:
            token = fh.read().strip()
    result = rm.verify(args.owner, args.repo, data, token, args.branch)
    emit("verify %s/%s@%s remote_files=%d"
         % (args.owner, args.repo, args.branch, result["remote_file_count"]))
    emit("matched=%d mismatched=%d missing=%d extra=%d public=%s"
         % (len(result["matched"]), len(result["mismatched"]),
            len(result["missing_on_remote"]), len(result["extra_on_remote"]),
            result["public"]))
    for item in result["mismatched"]:
        emit("  MISMATCH %s local=%s remote=%s"
             % (deliverables.ascii_ok(item["path"]), item["local"][:10], item["remote"][:10]))
    for path in result["missing_on_remote"]:
        emit("  MISSING_ON_REMOTE %s" % deliverables.ascii_ok(path))
    for path in result["extra_on_remote"]:
        emit("  EXTRA_ON_REMOTE %s" % deliverables.ascii_ok(path))
    if result.get("ignored_on_remote"):
        emit("ignored_on_remote=%d %s"
             % (len(result["ignored_on_remote"]),
                " ".join(deliverables.ascii_ok(p) for p in result["ignored_on_remote"])))
    emit("verdict=%s" % ("IDENTICAL" if result["ok"] else "DIFFERS"))
    return 0 if result["ok"] else 3


def cmd_doctor(args):
    checks = []
    checks.append(("python", sys.version.split()[0], True))
    checks.append(("cwd_ascii", str(ord(max(args.probe, default="/")) < 128), None))
    checks.append(("node_env", "set" if os.environ.get("COGSEED_NODE") else "missing",
                   bool(os.environ.get("COGSEED_NODE"))))
    checks.append(("pc_env", "set" if os.environ.get("COGSEED_PC_DIR") else "missing",
                   bool(os.environ.get("COGSEED_PC_DIR"))))
    token = os.environ.get("GITHUB_TOKEN", "")
    checks.append(("github_token", "set" if token else "missing", bool(token)))
    try:
        ok, note = rm.is_public("octocat", "Hello-World")
        checks.append(("api_github", note if ok else "unreachable", ok))
    except Exception as exc:  # network is a real precondition, never assume it
        checks.append(("api_github", "error: %s" % exc, False))
    emit("doctor")
    for name, value, ok in checks:
        flag = "ok" if ok else ("warn" if ok is None else "fail")
        emit("  [%s] %-14s %s" % (flag, name, deliverables.ascii_ok(value)))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="subkit", description="pre-submission and acceptance toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("preflight", help="check required deliverable names in a workspace")
    p1.add_argument("workspace")
    p1.add_argument("--required", required=True, help="comma separated pattern list from the challenge")
    p1.add_argument("--detail", default="preflight.txt")
    p1.set_defaults(func=cmd_preflight)

    p2 = sub.add_parser("manifest", help="write a byte-level manifest")
    p2.add_argument("workspace")
    p2.add_argument("--out", default="manifest.json")
    p2.set_defaults(func=cmd_manifest)

    p3 = sub.add_parser("verify", help="byte-level compare local manifest with a GitHub repo")
    p3.add_argument("--manifest", required=True)
    p3.add_argument("--owner", required=True)
    p3.add_argument("--repo", required=True)
    p3.add_argument("--branch", default="main")
    p3.add_argument("--token-env", default="GITHUB_TOKEN")
    p3.add_argument("--token-file", default="")
    p3.set_defaults(func=cmd_verify)

    p4 = sub.add_parser("doctor", help="check machine preconditions")
    p4.add_argument("--probe", default="/")
    p4.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
