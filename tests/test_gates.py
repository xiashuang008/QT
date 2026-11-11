import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from runtime.dailyflow.gates import (
    check_consistency,
    check_identity,
    check_numbers,
    check_timing,
)


class GateTests(unittest.TestCase):
    def test_number_mismatch_reports_difference(self):
        metrics = {
            "discount_amount": {
                "display_name": "贴现量",
                "value": 60,
                "raw_value": "60",
                "unit": "亿元",
                "data_date": "2025-09-30",
                "available_at": "2025-10-01T09:00:00+08:00",
            }
        }

        result = check_numbers("- 贴现量：70 亿元", metrics)

        self.assertFalse(result.passed)
        self.assertEqual(result.issues[0]["details"]["actual"], "70")
        self.assertEqual(result.issues[0]["details"]["expected"], "60")
        self.assertEqual(result.issues[0]["details"]["difference"], "10")

    def test_late_available_at_is_rejected(self):
        metrics = {
            "discount_amount": {
                "display_name": "贴现量",
                "value": 60,
                "raw_value": "60",
                "unit": "亿元",
                "data_date": "2025-09-30",
                "available_at": "2025-10-02T09:00:00+08:00",
            }
        }

        result = check_timing("- 贴现量：60 亿元", metrics, "2025-10-01T23:59:00+08:00")

        self.assertFalse(result.passed)
        self.assertEqual(result.issues[0]["details"]["field"], "discount_amount")

    def test_missing_role_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text(json.dumps({"conclusion": "passed"}), encoding="utf-8")
            reports = [{
                "task_id": "task-1",
                "report_id": "report-1",
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "self_contained": True,
            }]

            result = check_identity(reports, ["data-agent"])

        self.assertFalse(result.passed)
        self.assertTrue(any("角色身份" in issue["description"] for issue in result.issues))

    def test_holdout_and_development_cases_must_be_separate(self):
        baseline = {
            "holdout_cases": [{"case_id": "case-1", "checks": {"numbers": True}}],
            "development_cases": [],
        }
        candidate = {
            "holdout_cases": [{"case_id": "case-1", "checks": {"numbers": True}}],
            "development_cases": [{"case_id": "case-1", "checks": {"numbers": True}}],
        }

        result = check_consistency(candidate, baseline)

        self.assertFalse(result.passed)
        self.assertTrue(any("未分离" in issue["description"] for issue in result.issues))


if __name__ == "__main__":
    unittest.main()
