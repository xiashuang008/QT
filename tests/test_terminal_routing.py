import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from runtime.dailyflow.controller import ControlStateWriteForbidden, FlowController
from runtime.dailyflow.states import FlowState, TerminalResult


class TerminalAndRoutingTests(unittest.TestCase):
    def test_revision_exhaustion_is_not_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FlowController("exhausted-task", directory)
            controller.increment_revision()
            controller.increment_revision()

            result = controller.stop(TerminalResult.EXHAUSTED, "修订轮次用尽", "generator-lead")
            state = controller.read_state()
            trace = [json.loads(line) for line in controller.trace_path.read_text(encoding="utf-8").splitlines()]

            self.assertEqual(result["decision"], "stop")
            self.assertNotIn(state["status"], {"verified", "approved"})
            self.assertEqual(state["terminal_result"], "exhausted")
            self.assertFalse(state["acceptance_passed"])
            self.assertFalse(state["publication_allowed"])
            self.assertFalse(TerminalResult.EXHAUSTED.acceptance_passed)
            self.assertEqual(trace[-1]["event"], "stop")
            self.assertEqual(trace[-1]["payload"]["terminal_result"], "exhausted")

    def test_route_waits_for_missing_input(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FlowController("wait-task", directory)
            result = controller.route_submission("data-agent", False, True, False, input_version="v1")

            self.assertEqual(result["decision"], "wait")
            self.assertFalse(result["advanced"])
            self.assertEqual(controller.read_state()["status"], "created")

    def test_route_repairs_invalid_submission_in_current_role(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FlowController("repair-task", directory)
            result = controller.route_submission("generator-lead", True, False, False)

            self.assertEqual(result["decision"], "repair")
            self.assertEqual(controller.read_state()["pending_role"], "generator-lead")
            self.assertEqual(controller.read_state()["status"], "created")

    def test_route_advances_only_after_checks_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FlowController("advance-task", directory)
            evidence = Path(directory) / "snapshot.json"
            evidence.write_text("{}", encoding="utf-8")
            dependency = {"path": str(evidence), "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(), "verified": True}

            result = controller.route_submission(
                "data-agent",
                True,
                True,
                True,
                target=FlowState.DATA_READY,
                evidence_paths=[(evidence, "snapshot")],
                dependencies=[dependency],
            )

            self.assertEqual(result["decision"], "advance")
            self.assertEqual(controller.read_state()["status"], "data_ready")

    def test_route_stops_when_terminal_condition_is_met(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FlowController("stop-task", directory)
            result = controller.route_submission("data-agent", True, True, False, terminal_result=TerminalResult.BLOCKED, terminal_reason="依赖不安全")

            self.assertEqual(result["decision"], "stop")
            self.assertEqual(controller.read_state()["terminal_result"], "blocked")
            self.assertEqual(controller.read_state()["status"], "created")

    def test_input_version_change_starts_new_case(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FlowController("versioned-task", directory)
            controller.route_submission("data-agent", False, True, False, input_version="v1")

            result = controller.route_submission("data-agent", False, True, False, input_version="v2")
            new_controller = result["controller"]

            self.assertEqual(result["decision"], "new_case")
            self.assertNotEqual(new_controller.task_id, controller.task_id)
            self.assertEqual(new_controller.read_state()["artifacts"], [])
            self.assertTrue(new_controller.read_state()["dependencies_rebuild_required"])

    def test_role_cannot_write_control_state(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FlowController("exclusive-task", directory)
            before = controller.state_path.read_bytes()

            with self.assertRaises(ControlStateWriteForbidden):
                controller.write_role_report(controller.state_path, {"status": "verified"}, "generator-lead")
            self.assertEqual(controller.state_path.read_bytes(), before)

            report = controller.write_role_report(Path(directory) / "report.json", {"conclusion": "passed"}, "generator-lead")
            self.assertFalse(report["control_state_updated"])
            self.assertEqual(controller.state_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
