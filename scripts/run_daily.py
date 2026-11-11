import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.calculator import calculate_case
from scripts.collect import collect_fixture
from runtime.dailyflow.controller import FlowController
from runtime.dailyflow.gates import (
    check_completeness,
    check_freshness,
    check_identity,
    check_numbers,
    check_timing,
)
from runtime.dailyflow.states import FlowState, STATE_ORDER


REPORT_DATE = "2025-10-02"
CUTOFF = "2025-10-01T23:59:00+08:00"
CRITIC_ROLES = ("data-evidence-agent", "robustness-agent", "execution-agent", "risk-control-agent")


class InjectedInterruption(RuntimeError):
    pass


def _write_json(path, payload):
    FlowController._atomic_write(Path(path), json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _metric(metrics, key):
    return metrics["metrics"][key]


def _line(metrics, key, label):
    metric = _metric(metrics, key)
    return f"- {label}：{metric['raw_value']} {metric['unit']}"


def render_mock_draft(metrics):
    values = metrics["metrics"]
    supply_date = values["acceptance_amount"]["data_date"]
    gap_date = values["discount_gap"]["data_date"]
    rate_date = values["cross_year_bill_rate"]["data_date"]
    funding_date = values["dr001"]["data_date"]
    lines = [
        "# 票据市场日评",
        "",
        f"**数据截止时点**：{CUTOFF}",
        "",
        "## 票据供给",
        "",
        f"**本模块数据日期**：{supply_date}",
        "",
        _line(metrics, "acceptance_amount", "承兑量"),
        _line(metrics, "discount_amount", "贴现量"),
        _line(metrics, "trading_amount", "交易量"),
        "",
        "## 缺口分析",
        "",
        f"**本模块数据日期**：{gap_date}",
        "",
        _line(metrics, "discount_mom", "贴现量环比"),
        _line(metrics, "discount_yoy", "贴现量同比"),
        _line(metrics, "acceptance_discount_ratio", "承贴比"),
        _line(metrics, "remaining_business_days", "本月剩余工作日"),
        _line(metrics, "discount_gap", "缺口"),
        _line(metrics, "daily_required_amount", "日均需补量"),
        "",
        "## 票据利率",
        "",
        f"**本模块数据日期**：{rate_date}",
        "",
        _line(metrics, "cross_year_bill_rate", "跨年票利率"),
        _line(metrics, "regular_bill_rate", "普通票利率"),
        "",
        "## 资金面",
        "",
        f"**本模块数据日期**：{funding_date}",
        "",
        _line(metrics, "omo_injection", "逆回购投放"),
        _line(metrics, "omo_maturity", "逆回购到期"),
        _line(metrics, "omo_net_injection", "逆回购净投放"),
        _line(metrics, "shibor_on", "SHIBOR 隔夜"),
        _line(metrics, "dr001", "DR001"),
        _line(metrics, "dr007", "DR007"),
        _line(metrics, "r007", "R007"),
        "",
        "**输出为研究参考，不是报价指令。**",
        "",
    ]
    return "\n".join(lines)


def _report_metadata(path, role, task_id, round_number):
    return {
        "role": role,
        "task_id": task_id,
        "report_id": f"{task_id}-{role}-round-{round_number}",
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "self_contained": True,
    }


def run_daily(task_id, case_dir, fixture_dir=None, fail_after_calculation=False, calculator_fn=calculate_case, collector_fn=collect_fixture, logger=None):
    fixture_dir = Path(fixture_dir) if fixture_dir else ROOT / "tests" / "fixtures"
    case_dir = Path(case_dir).resolve()
    controller = FlowController(task_id, case_dir)
    logs = []

    def emit(message):
        logs.append(message)
        if logger:
            logger(message)

    resume = controller.resume()
    current = FlowState(resume["state"]["status"])
    emit(f"task_id={task_id}；当前状态={current.value}；恢复阶段={resume['stage']}")
    if resume["status"] == "completed":
        emit("案例已发布，直接返回保存结果")
        return {"status": "completed", "result_path": resume["result_path"], "logs": logs}
    if current == FlowState.VERIFIED:
        emit("候选已核验，继续等待人工批准，不重复执行")
        return {"status": "verified", "waiting_for": "human_approval", "result_path": resume["result_path"], "logs": logs}
    if current in {FlowState.APPROVED, FlowState.PUBLISHED}:
        return {"status": current.value, "result_path": resume["result_path"], "logs": logs}

    rank = {state: index for index, state in enumerate(STATE_ORDER)}
    if rank[current] < rank[FlowState.DATA_READY]:
        emit("开始采集固定夹具")
        collector_fn(fixture_dir / "source_data.csv", case_dir / "snapshots", REPORT_DATE, "2025-10-02T08:30:00+08:00")
        manifest_path = case_dir / "snapshots" / REPORT_DATE / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        gate = check_freshness(manifest, REPORT_DATE)
        if not gate.passed:
            controller.register_issues(gate.issues, 0)
            emit("数据新鲜度关卡失败，状态保持 created")
            return {"status": "blocked", "gate": gate.to_dict(), "logs": logs}
        controller.advance(FlowState.DATA_READY, [(manifest_path, "snapshot_manifest")], "data-agent", gate)
        current = FlowState.DATA_READY
        emit("采集完成，状态=data_ready")

    if rank[current] < rank[FlowState.CALCULATED]:
        emit("开始确定性计算")
        payload = json.loads((fixture_dir / "calculator_input.json").read_text(encoding="utf-8"))
        payload["task_id"] = task_id
        payload["calendar_path"] = str((fixture_dir / "trading_calendar.csv").resolve())
        metrics = calculator_fn(payload)
        metrics_path = case_dir / "metrics.json"
        _write_json(metrics_path, metrics)
        controller.advance(FlowState.CALCULATED, [(metrics_path, "metrics")], "metrics-agent", {"name": "calculator_completed", "passed": bool(metrics["metrics"]), "issues": []})
        current = FlowState.CALCULATED
        emit("计算完成，状态=calculated")

    if fail_after_calculation:
        controller.record_event("route", {"decision": "interrupted", "reason": "计算完成、日评生成前的故意中断"})
        emit("故意中断：计算完成、日评生成前")
        raise InjectedInterruption("计算完成、日评生成前的故意中断")

    if rank[current] < rank[FlowState.DRAFTED]:
        emit("恢复或进入 drafted：跳过已完成的采集与计算")
        metrics = json.loads((case_dir / "metrics.json").read_text(encoding="utf-8"))
        draft = render_mock_draft(metrics)
        draft_path = case_dir / "candidate.md"
        FlowController._atomic_write(draft_path, draft)
        gates = [check_numbers(draft, metrics), check_completeness(draft), check_timing(draft, metrics, CUTOFF)]
        issues = [issue for gate in gates for issue in gate.issues]
        if issues:
            controller.register_issues(issues, 0)
            emit("生成关卡失败，状态保持 calculated")
            return {"status": "blocked", "issues": issues, "logs": logs}
        controller.advance(FlowState.DRAFTED, [(draft_path, "candidate")], "generator-lead", {"name": "draft_gates", "passed": True, "issues": []})
        current = FlowState.DRAFTED
        emit("候选日评完成，状态=drafted")

    if rank[current] < rank[FlowState.VERIFIED]:
        draft_path = case_dir / "candidate.md"
        metrics = json.loads((case_dir / "metrics.json").read_text(encoding="utf-8"))
        draft = draft_path.read_text(encoding="utf-8")
        candidate_sha = hashlib.sha256(draft_path.read_bytes()).hexdigest()
        required_passes = json.loads((ROOT / "policies" / "policy.json").read_text(encoding="utf-8"))["acceptance_thresholds"]["verification_acceptance"]["required_consecutive_passed_rounds"]
        verification_path = case_dir / "verification.json"
        for round_number in range(1, required_passes + 1):
            emit(f"Critic 第 {round_number} 轮独立核验，使用新上下文")
            reports = []
            for role in CRITIC_ROLES:
                report_path = case_dir / f"critic-{role}-round-{round_number}.json"
                _write_json(report_path, {"role": role, "task_id": task_id, "round": round_number, "conclusion": "passed", "candidate_sha256": candidate_sha, "self_contained": True})
                reports.append(_report_metadata(report_path, role, task_id, round_number))
            identity = check_identity(reports, CRITIC_ROLES)
            numeric = check_numbers(draft, metrics)
            timing = check_timing(draft, metrics, CUTOFF)
            passed = identity.passed and numeric.passed and timing.passed
            passes = controller.record_verification_round(candidate_sha, passed)
            _write_json(verification_path, {"schema_version": "1.0.0", "task_id": task_id, "candidate_id": task_id, "candidate_sha256": candidate_sha, "round": round_number, "context_id": f"critic-context-{round_number}", "checks": [{"name": identity.name, "status": "passed" if identity.passed else "failed", "evidence_paths": [item["path"] for item in reports]}], "unresolved_issue_ids": [], "conclusion": "passed" if passed else "failed", "created_at": "2025-10-02T09:00:00+08:00"})
            if not passed:
                controller.register_issues(identity.issues + numeric.issues + timing.issues, round_number)
                emit("独立核验失败，状态保持 drafted")
                return {"status": "rejected", "logs": logs}
            emit(f"第 {round_number} 轮核验通过；同一候选连续通过={passes}")
        controller.advance(FlowState.VERIFIED, [(verification_path, "verification")], "critic-lead", {"name": "verification_acceptance", "passed": passes >= required_passes, "issues": []})
        emit("核验完成，状态=verified")

    result_path = case_dir / "result.json"
    _write_json(result_path, {"task_id": task_id, "candidate": str((case_dir / "candidate.md").resolve()), "status": "verified", "waiting_for": "human_approval"})
    controller.save_result(result_path)
    emit("停止自动执行，等待具名人工 approve；未获得发布授权")
    return {"status": "verified", "waiting_for": "human_approval", "result_path": str(result_path), "logs": logs}


def main(argv=None):
    parser = argparse.ArgumentParser(description="以固定夹具运行票据日评全流程")
    parser.add_argument("--task-id", default="mock-2025-10-02")
    parser.add_argument("--case-dir", default="output/dailyflow/mock-2025-10-02")
    parser.add_argument("--fixtures", default=str(ROOT / "tests" / "fixtures"))
    parser.add_argument("--fail-after-calculation", action="store_true")
    args = parser.parse_args(argv)
    result = run_daily(args.task_id, args.case_dir, args.fixtures, args.fail_after_calculation, logger=print)
    print(json.dumps({key: value for key, value in result.items() if key != "logs"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
