import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_daily import run_daily
from runtime.dailyflow.controller import FlowController
from runtime.dailyflow.evolution import append_version_record, rollback_version, validate_approval, validate_evolution_proposal
from runtime.dailyflow.gates import check_completeness, check_identity, check_numbers, check_timing, check_wording, check_consistency
from runtime.dailyflow.states import FlowState


TASK_ID = "daily-2026-11-11"
REPORT_DATE = "2026-11-11"
CUTOFF = "2026-11-10T23:59:00+08:00"
FIXTURES = ROOT / "tests" / "fixtures" / TASK_ID
OUTPUT = ROOT / "output" / "demo-daily-2026-11-11"
EXAMPLES = ROOT / "examples"
EVIDENCE = ROOT / "evidence"


def write_text(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json(path, payload):
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def copy_file(source, target):
    write_text(target, Path(source).read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reset_directory(path):
    if Path(path).exists():
        shutil.rmtree(path)


def rejection_case(name, trigger, gate, role):
    case_dir = ROOT / "output" / f"rejection-{name}"
    reset_directory(case_dir)
    controller = FlowController(f"rejection-{name}", case_dir)
    before = controller.read_state()["status"]
    assert not gate.passed, name
    controller.register_issues(gate.issues, 1)
    route = controller.route_submission(role, True, True, gate.passed)
    after = controller.read_state()["status"]
    assert before == after == "created"
    trace_target = EVIDENCE / "trace" / f"rejection-{name}.jsonl"
    issues_target = EVIDENCE / "issues" / f"rejection-{name}.json"
    copy_file(controller.trace_path, trace_target)
    copy_file(controller.issues_path, issues_target)
    record = {
        "scenario": name,
        "trigger": trigger,
        "gate": gate.to_dict(),
        "state_before": before,
        "state_after": after,
        "route": route,
        "trace_path": str(trace_target),
        "issues_path": str(issues_target),
    }
    write_json(EVIDENCE / "rejections" / f"{name}.json", record)
    return record


def main():
    reset_directory(OUTPUT)
    result = run_daily(TASK_ID, OUTPUT, FIXTURES, report_date=REPORT_DATE, cutoff=CUTOFF)
    assert result["status"] == "verified"
    candidate_path = OUTPUT / "rounds" / "round-001" / "generator" / "candidate.md"
    metrics_path = OUTPUT / "rounds" / "round-001" / "generator" / "metrics.json"
    snapshot_path = OUTPUT / "snapshots" / REPORT_DATE / "manifest.json"
    draft = candidate_path.read_text(encoding="utf-8")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert check_numbers(draft, metrics).passed
    assert check_completeness(draft, metrics).passed
    assert check_timing(draft, metrics, CUTOFF).passed

    example_review = EXAMPLES / "2026-11-11-daily-review.md"
    example_metrics = EXAMPLES / "2026-11-11-metrics.json"
    example_snapshot = EXAMPLES / "2026-11-11-snapshot-manifest.json"
    copy_file(candidate_path, example_review)
    copy_file(metrics_path, example_metrics)
    copy_file(snapshot_path, example_snapshot)

    violating_metrics = copy.deepcopy(metrics)
    violating_metrics["metrics"]["dr001"]["available_at"] = "2026-11-11T18:00:00+08:00"
    timing_gate = check_timing(draft, violating_metrics, CUTOFF)
    assert not timing_gate.passed
    write_json(EXAMPLES / "2026-11-11-timing-violation.json", {
        "scenario": "DR001 的可得时点晚于信息截止时点",
        "field": "dr001",
        "cutoff": CUTOFF,
        "available_at": "2026-11-11T18:00:00+08:00",
        "metrics": violating_metrics,
        "gate_result": timing_gate.to_dict(),
    })

    for source in (OUTPUT / "state-snapshots").glob("*.json"):
        copy_file(source, EVIDENCE / "state-snapshots" / source.name)
    copy_file(OUTPUT / "trace.jsonl", EVIDENCE / "trace" / "daily-run-2026-11-11.jsonl")
    copy_file(OUTPUT / "issues.json", EVIDENCE / "issues" / "daily-run-2026-11-11.json")

    numeric_draft = draft.replace("- 贴现量：75 亿元", "- 贴现量：80 亿元")
    numeric_gate = check_numbers(numeric_draft, metrics)
    numeric = rejection_case("numbers", "正文贴现量由 75 改为 80，指标结果仍为 75", numeric_gate, "generator-lead")
    timing = rejection_case("timing", "DR001 available_at 改为 2026-11-11T18:00:00+08:00", timing_gate, "generator-lead")

    identity_case = ROOT / "output" / "identity-report.json"
    write_json(identity_case, {"conclusion": "passed"})
    identity_gate = check_identity([{
        "task_id": TASK_ID,
        "report_id": "missing-role-report",
        "path": str(identity_case),
        "sha256": sha256(identity_case),
        "self_contained": True,
    }], ["data-evidence-agent"])
    identity = rejection_case("identity", "专项报告元数据缺少 role", identity_gate, "critic-lead")

    rejection_lines = [
        "# 拒绝路径演示",
        "",
        "本文件由 `tests/demo_daily_run.py` 调用真实关卡与控制器生成，全部使用合成数据。",
        "",
    ]
    for record in [numeric, timing, identity]:
        first_issue = record["gate"]["issues"][0]
        rejection_lines.extend([
            f"## {record['scenario']}",
            "",
            f"- 触发条件：{record['trigger']}",
            f"- 命中的关卡：`{record['gate']['name']}`，返回 `FAIL`。",
            f"- 返回问题项：`{first_issue['id']}`；{first_issue['description']}",
            f"- 问题明细：`{json.dumps(first_issue['details'], ensure_ascii=False)}`",
            f"- 状态停留：`{record['state_before']}` → `{record['state_after']}`，未推进。",
            f"- trace 路由决策：`{record['route']['decision']}`；{record['route']['reason']}",
            "",
        ])
    write_text(EVIDENCE / "rejection-demo.md", "\n".join(rejection_lines))

    reset_directory(ROOT / "output" / "issues-demo")
    issues_controller = FlowController("issues-demo", ROOT / "output" / "issues-demo")
    issues_controller.register_issues(numeric_gate.issues, 1)
    write_json(EVIDENCE / "issues" / "round-001.json", {"issues": issues_controller.read_issues()})
    issue_ids = [issue["id"] for issue in issues_controller.read_issues()]
    issues_controller.carry_forward_issues(2, [], [], False)
    assert all(issue["status"] == "open" for issue in issues_controller.read_issues())
    write_json(EVIDENCE / "issues" / "round-002.json", {"issues": issues_controller.read_issues()})
    issues_controller.carry_forward_issues(3, issue_ids, issue_ids, True, example_review)
    assert all(issue["status"] == "resolved" for issue in issues_controller.read_issues())
    write_json(EVIDENCE / "issues" / "resolved.json", {"issues": issues_controller.read_issues()})
    copy_file(issues_controller.trace_path, EVIDENCE / "trace" / "issues-demo.jsonl")

    candidate_sha = sha256(example_review)
    approval = {
        "schema_version": "1.0.0",
        "approval_id": "approval-2026-11-11-v2",
        "task_id": TASK_ID,
        "version": "v2026.11.11.2",
        "candidate_sha256": candidate_sha,
        "approver_name": "示例批准人甲",
        "approver_role": "票据交易台授权人工批准人",
        "conclusion": "approve",
        "approved_at": "2026-11-11T10:00:00+08:00",
        "expires_at": "2026-11-12T10:00:00+08:00",
    }
    approval_path = EVIDENCE / "approval-sample" / "approval-v2026.11.11.2.json"
    write_json(approval_path, approval)
    original_validation = validate_approval(approval, approval["version"], candidate_sha, "2026-11-11T10:30:00+08:00")
    version_validation = validate_approval(approval, "v2026.11.11.3", candidate_sha, "2026-11-11T10:30:00+08:00")
    candidate_validation = validate_approval(approval, approval["version"], "0" * 64, "2026-11-11T10:30:00+08:00")
    assert original_validation["valid"]
    assert not version_validation["valid"]
    assert not candidate_validation["valid"]
    write_json(EVIDENCE / "approval-sample" / "validation.json", {
        "original": original_validation,
        "version_changed": version_validation,
        "candidate_changed": candidate_validation,
    })

    baseline_approval = dict(approval)
    baseline_approval.update({"approval_id": "approval-2026-11-11-v1", "version": "v2026.11.11.1", "approved_at": "2026-11-10T10:00:00+08:00"})
    baseline_approval_path = EVIDENCE / "approval-sample" / "approval-v2026.11.11.1.json"
    write_json(baseline_approval_path, baseline_approval)

    proposal = {
        "proposal_id": "evolution-2026-11-11",
        "failure_reference": "示例：结论段呈现顺序需要改进",
        "allowed_changes": ["prompts/report_writer_system.md", "skills/start/SKILL.md"],
        "acceptance_standard": "unchanged",
        "lower_acceptance": False,
        "non_goals": ["不修改验收规则", "不修改阈值", "不修改控制器代码"],
    }
    proposal_validation = validate_evolution_proposal(proposal)
    assert proposal_validation["passed"]
    write_json(EVIDENCE / "evolution" / "proposal.json", proposal)
    write_json(EVIDENCE / "evolution" / "proposal-validation.json", proposal_validation)

    baseline = {"holdout_cases": [{"case_id": "holdout-2026-11-10", "checks": {"numbers": True, "timing": True, "completeness": True}}], "development_cases": [{"case_id": "dev-2026-11-09", "checks": {"numbers": True}}]}
    candidate = {"holdout_cases": [{"case_id": "holdout-2026-11-10", "checks": {"numbers": True, "timing": True, "completeness": True}}], "development_cases": [{"case_id": "dev-2026-11-11", "checks": {"numbers": True}}]}
    regression = check_consistency(candidate, baseline)
    assert regression.passed
    critic_gates = [check_numbers(draft, metrics), check_completeness(draft, metrics), check_timing(draft, metrics, CUTOFF), check_wording(draft)]
    assert all(gate.passed for gate in critic_gates)

    registry = EVIDENCE / "version-registry.jsonl"
    write_text(registry, "")
    baseline_version = "v2026.11.11.1"
    candidate_version = "v2026.11.11.2"
    for version, approval_file, event, status in [
        (baseline_version, baseline_approval_path, "registered", "previous"),
        (candidate_version, approval_path, "adopted", "active"),
    ]:
        version_evidence = {
            "version": version,
            "candidate_sha256": candidate_sha,
            "candidate_path": str(example_review),
            "metrics_path": str(example_metrics),
            "baseline_path": str(example_review),
            "regression": regression.to_dict(),
            "critic_gates": [gate.to_dict() for gate in critic_gates],
        }
        version_path = EVIDENCE / "evolution" / "versions" / f"{version}.json"
        write_json(version_path, version_evidence)
        append_version_record(registry, {
            "schema_version": "1.0.0",
            "event": event,
            "version": version,
            "task_id": TASK_ID,
            "parent_version": baseline_version if version == candidate_version else None,
            "status": status,
            "artifacts": [{"kind": "candidate", "path": str(example_review), "sha256": candidate_sha}],
            "baseline_comparison": regression.to_dict(),
            "regression_result": regression.to_dict(),
            "approval_record_path": str(approval_file),
            "rollback_target": baseline_version if version == candidate_version else None,
            "registered_at": "2026-11-11T10:45:00+08:00",
        })
    rollback = rollback_version(
        registry,
        candidate_version,
        baseline_version,
        "获批候选回滚到先前版本指针；回滚后须在新案例中重新核验",
        "2026-11-11T11:00:00+08:00",
        metadata={
            "task_id": TASK_ID,
            "parent_version": candidate_version,
            "artifacts": [{"kind": "candidate", "path": str(example_review), "sha256": candidate_sha}],
            "baseline_comparison": regression.to_dict(),
            "regression_result": regression.to_dict(),
            "approval_record_path": str(baseline_approval_path),
            "rollback_target": baseline_version,
            "registered_at": "2026-11-11T11:00:00+08:00",
        },
    )
    write_json(EVIDENCE / "evolution" / "current-version.json", {
        "active_version": baseline_version,
        "rolled_back_from": candidate_version,
        "requires_new_case_verification": True,
        "rollback": rollback,
    })

    evolution_lines = [
        "# 演进、采纳与回滚演示",
        "",
        "本文件由真实回归关卡、批准校验和版本注册函数生成，使用固定基线与合成数据。",
        "",
        "## 固定基线与限定范围改动",
        "",
        f"- 基线版本：`{baseline_version}`；候选版本：`{candidate_version}`；候选 SHA-256：`{candidate_sha}`。",
        "- 允许改动仅限 `prompts/report_writer_system.md` 与 `skills/start/SKILL.md`。",
        "- 提案明确不修改验收规则、阈值或控制器代码，且 `lower_acceptance=false`。",
        "",
        "## 比较、回归与 Critic 审查",
        "",
        f"- `check_consistency`：{'PASS' if regression.passed else 'FAIL'}；留出案例与开发案例分离。",
        f"- Critic 代码关卡：{', '.join(gate.name + '=PASS' for gate in critic_gates)}。",
        f"- 人工批准校验：`{json.dumps(original_validation, ensure_ascii=False)}`。",
        "",
        "## 采纳与回滚",
        "",
        f"- 采纳：`{candidate_version}` 经人工批准后写入版本注册表并标记为启用。",
        f"- 回滚：`{candidate_version}` → `{baseline_version}`；新旧版本证据均保留在 `evidence/evolution/versions/`。",
        "- 回滚记录明确 `requires_new_case_verification=true`，回滚后的行为必须在新案例中重新核验，不复用旧批准。",
        "",
    ]
    write_text(EVIDENCE / "evolution-demo.md", "\n".join(evolution_lines))

    reset_directory(ROOT / "output" / "approval-state-demo")
    state_controller = FlowController("approval-state-demo", ROOT / "output" / "approval-state-demo")
    for target in [FlowState.DATA_READY, FlowState.CALCULATED, FlowState.DRAFTED, FlowState.VERIFIED, FlowState.APPROVED, FlowState.PUBLISHED]:
        advanced = state_controller.advance(target, [(approval_path, "approval_evidence")], "orchestrator", {"name": "demo_gate", "passed": True, "issues": []})
        assert advanced
    for name in ["approved.json", "published.json"]:
        copy_file(ROOT / "output" / "approval-state-demo" / "state-snapshots" / name, EVIDENCE / "state-snapshots" / name)
    copy_file(ROOT / "output" / "approval-state-demo" / "trace.jsonl", EVIDENCE / "trace" / "approval-state-demo.jsonl")

    print(json.dumps({
        "daily_review": str(example_review),
        "timing_violation": str(EXAMPLES / "2026-11-11-timing-violation.json"),
        "rejection_evidence": str(EVIDENCE / "rejection-demo.md"),
        "evolution_evidence": str(EVIDENCE / "evolution-demo.md"),
        "version_registry": str(registry),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
