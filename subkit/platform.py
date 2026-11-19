"""Calling the course platform without the two quoting traps.

Real failures this module encodes (2026-11, observed on this machine):
  * The helper signature is `<command> @payloadfile`; the "@" prefix is
    mandatory, otherwise the path is parsed as JSON and the call fails.
  * Building the command as a shell string loses quotes and breaks the JSON,
    so argv is always a list and the shell is never used.
  * `list-my-submissions` lags behind `get-task`. A submission that is not in
    the list yet must not be re-sent; `get-task` is the authority.
  * `get-evaluation` returns NOT_FOUND before the async score lands. That is
    "not yet", not "failed".
"""
import json
import os
import subprocess
import time

TERMINAL_OK = {"completed", "succeeded", "success", "done"}
TERMINAL_BAD = {"failed", "error", "cancelled", "canceled", "timeout"}


def build_argv(node, runner, skill, command, payload_file, json_payload=None):
    """Return the exact argv for the skill runner, never a shell string.

    payload_file is passed as "@<path>"; if json_payload is given instead it is
    embedded as one single argv element, which is the only form PowerShell
    cannot split apart.
    """
    argv = [node, runner, skill, "runtime", "--", command]
    if payload_file:
        argv.append("@" + os.path.abspath(payload_file))
    elif json_payload is not None:
        argv.append(json.dumps(json_payload, ensure_ascii=True))
    return argv


def run_skill(command, payload_file=None, json_payload=None, timeout=300):
    node = os.environ.get("COGSEED_NODE") or "node"
    pcdir = os.environ.get("COGSEED_PC_DIR") or ""
    runner = os.path.join(pcdir, "bin", "run-skill.cjs")
    argv = build_argv(node, runner, "eduseed-student-submit", command,
                      payload_file, json_payload)
    proc = subprocess.run(argv, capture_output=True, timeout=timeout, shell=False)
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace")
    return {"rc": proc.returncode, "stdout": out, "stderr": err,
            "argv_len": len(argv)}


def parse_json(out):
    """The runner prints human lines around the JSON payload; take the first object."""
    text = out.strip()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    try:
        return json.loads(text)
    except ValueError:
        return None


def decide(task_state, listed, submission_id=None):
    """Single decision point for polling.

    task_state : status string from get-task (authoritative)
    listed     : True when list-my-submissions already contains the submission
    Returns one of: done | failed | poll | resubmit
    """
    state = (task_state or "").strip().lower()
    if state in TERMINAL_OK:
        return "done"
    if state in TERMINAL_BAD:
        return "failed"
    if state in ("pending", "processing", "queued", "running", ""):
        return "poll"
    return "poll"


def poll(task_id, interval=5.0, timeout=180.0, sleeper=time.sleep, fetch=None):
    """Poll get-task until it reports a terminal state.

    Returns a dict with attempts, status, payload and elapsed seconds. A
    submission id is returned as soon as the platform exposes it, even while
    the task is still running, so the caller never needs a second submission.
    """
    if fetch is None:
        raise ValueError("fetch callable is required")
    started = time.time()
    attempts = 0
    last = None
    while True:
        attempts += 1
        res = fetch(task_id)
        payload = (res or {}).get("json") or {}
        task = payload.get("task") or payload
        last = task
        status = str(task.get("status") or task.get("taskStatus") or "")
        verdict = decide(status, False)
        if verdict in ("done", "failed"):
            return {
                "attempts": attempts,
                "status": status,
                "verdict": verdict,
                "elapsed": round(time.time() - started, 1),
                "task": task,
            }
        if time.time() - started > timeout:
            return {
                "attempts": attempts,
                "status": status,
                "verdict": "timeout",
                "elapsed": round(time.time() - started, 1),
                "task": last,
            }
        sleeper(interval)
