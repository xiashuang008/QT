import json
import tempfile
import unittest
from pathlib import Path

from scripts.calculator import calculate_case
from scripts.collect import collect_fixture
from scripts.run_daily import InjectedInterruption, run_daily
from runtime.dailyflow.controller import EvidenceError, FlowController
from runtime.dailyflow.states import FlowState


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class ControllerTests(unittest.TestCase):
    def test_missing_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FlowController("task-1", directory)
            with self.assertRaisesRegex(EvidenceError, "证据文件缺失"):
                controller.register_evidence(Path(directory) / "missing.json", "data-agent", "snapshot")

    def test_failed_gate_does_not_advance_state(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FlowController("task-1", directory)
            evidence = Path(directory) / "snapshot.json"
            evidence.write_text("{}", encoding="utf-8")

            advanced = controller.advance(
                FlowState.DATA_READY,
                [(evidence, "snapshot")],
                "data-agent",
                {"name": "check_freshness", "passed": False, "issues": []},
            )

            self.assertFalse(advanced)
            self.assertEqual(controller.read_state()["status"], "created")

    def test_unresolved_issue_carries_into_second_round(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FlowController("task-1", directory)
            issue = {
                "id": "issue-1",
                "severity": "high",
                "check_type": "numbers",
                "affected_artifacts": [{"path": str(Path(directory) / "candidate.md"), "location": "票据供给"}],
                "description": "数字不一致",
                "evidence_required": ["修复后的数字对账证据"],
                "status": "open",
            }
            controller.register_issues([issue], 1)

            issues = controller.carry_forward_issues(2, [], [], False)

            self.assertEqual(issues[0]["status"], "open")
            self.assertEqual(issues[0]["last_failure"], "本轮修复遗漏，继续保持未解决")
            self.assertEqual(controller.read_state()["unresolved_issue_ids"], ["issue-1"])

    def test_only_critic_verification_closes_issue(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = FlowController("task-1", directory)
            evidence = Path(directory) / "fixed.json"
            evidence.write_text("{}", encoding="utf-8")
            issue = {
                "id": "issue-1",
                "severity": "high",
                "check_type": "numbers",
                "affected_artifacts": [{"path": str(evidence), "location": "票据供给"}],
                "description": "数字不一致",
                "evidence_required": ["修复后的数字对账证据"],
                "status": "open",
            }
            controller.register_issues([issue], 1)

            controller.carry_forward_issues(2, ["issue-1"], [], False, evidence)
            self.assertEqual(controller.read_issues()[0]["status"], "open")
            controller.carry_forward_issues(3, ["issue-1"], ["issue-1"], True, evidence)
            self.assertEqual(controller.read_issues()[0]["status"], "resolved")

    def test_recovery_does_not_repeat_collection_or_calculation(self):
        with tempfile.TemporaryDirectory() as directory:
            case_dir = Path(directory) / "case"
            first_calls = {"calculator": 0}

            def first_calculator(payload):
                first_calls["calculator"] += 1
                return calculate_case(payload)

            with self.assertRaises(InjectedInterruption):
                run_daily("recovery-task", case_dir, FIXTURES, fail_after_calculation=True, calculator_fn=first_calculator)

            self.assertEqual(first_calls["calculator"], 1)
            controller = FlowController("recovery-task", case_dir)
            self.assertEqual(controller.read_state()["status"], "calculated")
            second_calls = {"calculator": 0, "collector": 0}

            def second_calculator(payload):
                second_calls["calculator"] += 1
                return calculate_case(payload)

            def second_collector(*args):
                second_calls["collector"] += 1
                return collect_fixture(*args)

            result = run_daily(
                "recovery-task",
                case_dir,
                FIXTURES,
                calculator_fn=second_calculator,
                collector_fn=second_collector,
            )

            self.assertEqual(result["status"], "verified")
            self.assertEqual(second_calls, {"calculator": 0, "collector": 0})
            self.assertTrue(any("恢复阶段=drafted" in line for line in result["logs"]))
            self.assertEqual(controller.read_state()["status"], "verified")
            self.assertEqual(controller.read_state()["consecutive_verification_passes"], 2)


if __name__ == "__main__":
    unittest.main()
