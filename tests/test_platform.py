"""Regression tests for platform calls (failure class 4: quoting) and polling."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from subkit import platform as pf


class TestArgv(unittest.TestCase):
    def test_payload_file_uses_at_prefix(self):
        argv = pf.build_argv("node", "run.cjs", "skill", "submit-project", "p.json")
        self.assertTrue(argv[-1].startswith("@"))
        self.assertIn("p.json", argv[-1])

    def test_at_prefix_is_mandatory_by_construction(self):
        """Without '@' the helper parses the path as JSON and the call fails."""
        argv = pf.build_argv("node", "run.cjs", "skill", "get-task", "p.json")
        self.assertNotEqual(argv[-1], os.path.abspath("p.json"))

    def test_command_comes_before_payload(self):
        argv = pf.build_argv("node", "run.cjs", "skill", "get-task", "p.json")
        self.assertLess(argv.index("get-task"), len(argv) - 1)

    def test_inline_json_is_one_argv_element(self):
        payload = {"a": 1, "b": "x y z"}
        argv = pf.build_argv("node", "run.cjs", "skill", "cmd", None, payload)
        # node / runner / skill / runtime / -- / command / payload == 7 elements
        self.assertEqual(len(argv), 7)
        self.assertEqual(argv[3], "runtime")
        self.assertEqual(json.loads(argv[-1]), payload)

    def test_argv_is_a_list_never_a_shell_string(self):
        argv = pf.build_argv("node", "run.cjs", "skill", "cmd", "p.json")
        self.assertIsInstance(argv, list)
        self.assertTrue(all(isinstance(part, str) for part in argv))


class TestDecide(unittest.TestCase):
    def test_terminal_success_aliases(self):
        for state in ("completed", "succeeded", "success", "done", "COMPLETED"):
            self.assertEqual(pf.decide(state, False), "done")

    def test_terminal_failure_aliases(self):
        for state in ("failed", "error", "cancelled", "timeout"):
            self.assertEqual(pf.decide(state, False), "failed")

    def test_in_flight_states_poll(self):
        for state in ("pending", "processing", "queued", "running", ""):
            self.assertEqual(pf.decide(state, False), "poll")

    def test_list_lag_never_triggers_resubmit(self):
        """A submission missing from the list view is not a reason to resend."""
        self.assertNotEqual(pf.decide("pending", False), "resubmit")


class TestPoll(unittest.TestCase):
    def test_stops_on_terminal_state(self):
        states = iter(["pending", "processing", "completed"])

        def fetch(task_id):
            return {"json": {"task": {"status": next(states), "taskId": task_id}}}

        res = pf.poll("t1", interval=0, timeout=5, sleeper=lambda s: None, fetch=fetch)
        self.assertEqual(res["verdict"], "done")
        self.assertEqual(res["attempts"], 3)

    def test_submission_id_available_before_terminal(self):
        """The id must be reported even while the task is still running."""
        calls = []

        def fetch(task_id):
            calls.append(task_id)
            return {"json": {"task": {"status": "pending", "submissionId": "sub-1"}}}

        res = pf.poll("t1", interval=0, timeout=0, sleeper=lambda s: None, fetch=fetch)
        self.assertEqual(res["task"]["submissionId"], "sub-1")
        self.assertEqual(res["verdict"], "timeout")

    def test_timeout_is_reported_not_hidden(self):
        def fetch(task_id):
            return {"json": {"task": {"status": "processing"}}}

        res = pf.poll("t1", interval=0, timeout=0, sleeper=lambda s: None, fetch=fetch)
        self.assertEqual(res["verdict"], "timeout")

    def test_fetch_is_required(self):
        with self.assertRaises(ValueError):
            pf.poll("t1")


class TestParseJson(unittest.TestCase):
    def test_json_surrounded_by_log_lines(self):
        out = "[info] running\n{\"ok\": true}\n[info] done"
        self.assertEqual(pf.parse_json(out), {"ok": True})

    def test_garbage_returns_none(self):
        self.assertIsNone(pf.parse_json("no json here"))


if __name__ == "__main__":
    unittest.main()
