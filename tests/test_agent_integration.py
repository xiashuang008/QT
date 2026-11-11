import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.run_daily import CRITIC_ROLES, run_daily


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class AgentIntegrationTests(unittest.TestCase):
    def test_gates_cli_returns_machine_readable_judgement(self):
        with tempfile.TemporaryDirectory() as directory:
            draft = Path(directory) / "candidate.md"
            metrics = Path(directory) / "metrics.json"
            draft.write_text("- 贴现量：70 亿元", encoding="utf-8")
            metrics.write_text(json.dumps({"metrics": {"discount_amount": {"display_name": "贴现量", "value": 60, "raw_value": "60", "unit": "亿元", "data_date": "2025-09-30", "available_at": "2025-10-01T09:00:00+08:00"}}}), encoding="utf-8")

            completed = subprocess.run(
                [sys.executable, "runtime/dailyflow/gates.py", "check_numbers", "--draft", str(draft), "--metrics", str(metrics)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertFalse(result["passed"])
            self.assertEqual(result["issues"][0]["details"]["difference"], "10")

    def test_run_directory_layout_and_evidence_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            case_dir = Path(directory) / "output" / "layout-task"
            evidence_root = Path(directory) / "evidence"

            result = run_daily("layout-task", case_dir, FIXTURES, evidence_root=evidence_root)

            self.assertEqual(result["status"], "verified")
            required = [
                "state.json",
                "trace.jsonl",
                "issues.json",
                "result.json",
                "snapshots/2025-10-02/manifest.json",
                "rounds/round-001/decision.json",
                "rounds/round-002/decision.json",
            ]
            for round_number in [1, 2]:
                for name in ["data-agent.json", "timing-agent.json", "metrics-agent.json", "candidate.md"]:
                    required.append(f"rounds/round-{round_number:03d}/generator/{name}")
                for role in CRITIC_ROLES:
                    required.append(f"rounds/round-{round_number:03d}/critic/{role}.json")
                required.append(f"rounds/round-{round_number:03d}/critic/verification.json")
            for relative in required:
                self.assertTrue((case_dir / relative).is_file(), relative)

            archive_manifest = Path(result["archive_manifest"])
            archive = json.loads(archive_manifest.read_text(encoding="utf-8"))
            self.assertEqual(archive["task_id"], "layout-task")
            self.assertGreaterEqual(len(archive["artifacts"]), len(required))
            for artifact in archive["artifacts"]:
                path = Path(artifact["path"])
                self.assertTrue(path.is_file())
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact["sha256"])
            final = json.loads((case_dir / "result.json").read_text(encoding="utf-8"))
            self.assertTrue(final["acceptance_passed"])
            self.assertFalse(final["publication_allowed"])


if __name__ == "__main__":
    unittest.main()
