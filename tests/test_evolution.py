import json
import tempfile
import unittest
from pathlib import Path

from runtime.dailyflow.evolution import append_version_record, rollback_version, validate_approval, validate_evolution_proposal
from runtime.dailyflow.gates import check_completeness, check_numbers, check_timing


ROOT = Path(__file__).resolve().parents[1]
CUTOFF = "2026-11-10T23:59:00+08:00"


class EvolutionFunctionTests(unittest.TestCase):
    def test_proposal_cannot_expand_scope_or_lower_acceptance(self):
        self.assertFalse(validate_evolution_proposal({"allowed_changes": ["policies/policy.json"], "acceptance_standard": "unchanged"})["passed"])
        self.assertFalse(validate_evolution_proposal({"allowed_changes": ["prompts/report_writer_system.md"], "acceptance_standard": "lowered", "lower_acceptance": True})["passed"])

    def test_rollback_preserves_versions_and_requires_new_case(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "registry.jsonl"
            for version in ["v1", "v2"]:
                append_version_record(registry, {"version": version, "event": "adopted"})

            event = rollback_version(registry, "v2", "v1", "回归需要", "2026-11-11T11:00:00+08:00")
            records = [json.loads(line) for line in registry.read_text(encoding="utf-8").splitlines()]

            self.assertEqual([record["version"] for record in records], ["v1", "v2", "v1"])
            self.assertTrue(event["requires_new_case_verification"])


class DemoEvidenceTests(unittest.TestCase):
    def test_normal_example_and_timing_violation_reproduce_gate_results(self):
        draft = (ROOT / "examples" / "2026-11-11-daily-review.md").read_text(encoding="utf-8")
        metrics = json.loads((ROOT / "examples" / "2026-11-11-metrics.json").read_text(encoding="utf-8"))
        violation = json.loads((ROOT / "examples" / "2026-11-11-timing-violation.json").read_text(encoding="utf-8"))

        self.assertTrue(check_numbers(draft, metrics).passed)
        self.assertTrue(check_completeness(draft, metrics).passed)
        self.assertTrue(check_timing(draft, metrics, CUTOFF).passed)
        self.assertFalse(check_timing(draft, violation["metrics"], CUTOFF).passed)
        self.assertFalse(violation["gate_result"]["passed"])

    def test_rejection_evidence_contains_real_issues_and_stopped_states(self):
        for name, gate_name in [("numbers", "check_numbers"), ("timing", "check_timing"), ("identity", "check_identity")]:
            record = json.loads((ROOT / "evidence" / "rejections" / f"{name}.json").read_text(encoding="utf-8"))
            self.assertEqual(record["gate"]["name"], gate_name)
            self.assertFalse(record["gate"]["passed"])
            self.assertTrue(record["gate"]["issues"])
            self.assertEqual(record["state_before"], record["state_after"])
            self.assertEqual(record["route"]["decision"], "repair")
            self.assertTrue(Path(record["trace_path"]).is_file())

    def test_approval_invalidated_by_version_or_candidate_change(self):
        approval = json.loads((ROOT / "evidence" / "approval-sample" / "approval-v2026.11.11.2.json").read_text(encoding="utf-8"))
        validation = json.loads((ROOT / "evidence" / "approval-sample" / "validation.json").read_text(encoding="utf-8"))

        self.assertTrue(validate_approval(approval, approval["version"], approval["candidate_sha256"], "2026-11-11T10:30:00+08:00")["valid"])
        self.assertFalse(validation["version_changed"]["valid"])
        self.assertFalse(validation["candidate_changed"]["valid"])

    def test_issue_lifecycle_and_evolution_registry(self):
        round_two = json.loads((ROOT / "evidence" / "issues" / "round-002.json").read_text(encoding="utf-8"))
        resolved = json.loads((ROOT / "evidence" / "issues" / "resolved.json").read_text(encoding="utf-8"))
        self.assertTrue(all(issue["status"] == "open" for issue in round_two["issues"]))
        self.assertTrue(all(issue["status"] == "resolved" for issue in resolved["issues"]))

        records = [json.loads(line) for line in (ROOT / "evidence" / "version-registry.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(sum(record.get("event") == "adopted" for record in records), 1)
        self.assertEqual(sum(record.get("event") == "rollback" for record in records), 1)
        rollback = next(record for record in records if record.get("event") == "rollback")
        self.assertTrue(rollback["requires_new_case_verification"])
        for version in ["v2026.11.11.1", "v2026.11.11.2"]:
            self.assertTrue((ROOT / "evidence" / "evolution" / "versions" / f"{version}.json").is_file())

    def test_required_recovery_and_state_evidence_exists(self):
        for path in [
            "evidence/recovery-demo.md",
            "evidence/rejection-demo.md",
            "evidence/evolution-demo.md",
            "evidence/trace/recovery.jsonl",
            "evidence/state-snapshots/created.json",
            "evidence/state-snapshots/verified.json",
            "evidence/state-snapshots/approved.json",
            "evidence/state-snapshots/published.json",
        ]:
            self.assertTrue((ROOT / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
