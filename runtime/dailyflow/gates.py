import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


MODULES = ("票据供给", "缺口分析", "票据利率", "资金面")
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9.,])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?")
ALIASES = {
    "承兑量": "acceptance_amount",
    "贴现量": "discount_amount",
    "交易量": "trading_amount",
    "贴现量环比": "discount_mom",
    "贴现量同比": "discount_yoy",
    "承贴比": "acceptance_discount_ratio",
    "本月剩余工作日": "remaining_business_days",
    "缺口": "discount_gap",
    "日均需补量": "daily_required_amount",
    "跨年票利率": "cross_year_bill_rate",
    "普通票利率": "regular_bill_rate",
    "逆回购投放": "omo_injection",
    "逆回购到期": "omo_maturity",
    "逆回购净投放": "omo_net_injection",
    "公开市场操作净投放": "omo_net_injection",
    "公开市场操作净回笼": "omo_net_injection",
    "SHIBOR 隔夜": "shibor_on",
    "DR001": "dr001",
    "DR007": "dr007",
    "R007": "r007",
    "NCD 收益率曲线（资金面参照）": "ncd_yield_curve",
}


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    issues: list = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "name": self.name,
            "passed": self.passed,
            "issues": self.issues,
            "details": self.details,
        }


def _issue(check_type, description, affected="candidate.md", details=None):
    return {
        "id": f"{check_type}-{hashlib.sha256((description + str(details)).encode('utf-8')).hexdigest()[:12]}",
        "severity": "high",
        "check_type": check_type,
        "affected_artifacts": [{"path": str(Path(affected).resolve()), "location": details.get("location", "") if details else ""}],
        "description": description,
        "details": details or {},
        "evidence_required": ["修复后的候选产物及对应确定性证据"],
        "status": "open",
    }


def _metrics(metrics):
    return metrics.get("metrics", metrics)


def _decimal(value):
    text = str(value).replace(",", "").replace("%", "")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _metric_number(metric):
    value = _decimal(metric.get("raw_value", ""))
    if value is not None:
        return value
    if metric.get("value") is None:
        return None
    return _decimal(metric["value"])


def _line_label(line):
    return re.split("[:：]", line, maxsplit=1)[0].strip().lstrip("- ").strip("* ").strip()


def _metric_for_line(line, metrics):
    label = _line_label(line)
    if label in ALIASES and ALIASES[label] in metrics:
        return ALIASES[label]
    matches = []
    for key, metric in metrics.items():
        display_name = metric.get("display_name", "")
        if display_name and (label == display_name or display_name in line):
            matches.append((len(display_name), key))
    return max(matches)[1] if matches else None


def _numeric_lines(draft):
    for line in draft.splitlines():
        stripped = line.strip()
        if stripped.startswith("**数据截止时点**") or stripped.startswith("**本模块数据日期**"):
            continue
        if stripped.startswith("数据截止时点") or stripped.startswith("本模块数据日期"):
            continue
        yield line


def check_freshness(snapshot, expected_date):
    issues = []
    if snapshot.get("expected_trading_date") != str(expected_date):
        issues.append(_issue("freshness", "快照交易日不符合预期", details={"actual": snapshot.get("expected_trading_date"), "expected": str(expected_date)}))
    missing = [item.get("field") for item in snapshot.get("fields", []) if item.get("required", True) and (item.get("status") == "missing" or item.get("value") is None)]
    if not snapshot.get("fields"):
        issues.append(_issue("freshness", "快照没有任何字段"))
    for name in missing:
        issues.append(_issue("freshness", f"必需字段缺失：{name}", details={"field": name}))
    return GateResult("check_freshness", not issues, issues, {"missing_fields": missing})


def check_numbers(draft, metrics):
    metrics = _metrics(metrics)
    issues = []
    checked = 0
    for line in _numeric_lines(draft):
        metric_key = _metric_for_line(line, metrics)
        expected_metric = metrics.get(metric_key) if metric_key else None
        expected_value = _metric_number(expected_metric) if expected_metric else None
        for match in NUMBER_RE.finditer(line):
            token = match.group(0)
            actual = _decimal(token)
            if actual is None:
                continue
            checked += 1
            location = line.strip()
            if expected_metric is not None:
                if expected_value is None or actual != expected_value:
                    difference = str(actual - expected_value) if expected_value is not None else "不可计算"
                    issues.append(_issue("numbers", f"正文数值与指标结果不一致：{token}", details={"actual": token, "expected": expected_metric.get("raw_value"), "difference": difference, "metric": metric_key, "location": location}))
                following = line[match.end():].lstrip()
                if expected_metric.get("unit") == "%" and not token.endswith("%") and not following.startswith("%"):
                    issues.append(_issue("numbers", f"百分比缺少单位：{token}", details={"actual": token, "expected_unit": "%", "metric": metric_key, "location": location}))
                continue
            if not any(_metric_number(metric) == actual for metric in metrics.values()):
                issues.append(_issue("numbers", f"正文存在指标结果之外的数字：{token}", details={"actual": token, "expected": None, "difference": None, "location": location}))
    return GateResult("check_numbers", not issues, issues, {"checked_numbers": checked})


def check_completeness(draft, metrics=None):
    issues = []
    positions = []
    for module in MODULES:
        marker = f"## {module}"
        position = draft.find(marker)
        if position < 0:
            issues.append(_issue("completeness", f"缺少模块：{module}"))
        positions.append(position)
    present = [position for position in positions if position >= 0]
    if present != sorted(present):
        issues.append(_issue("completeness", "四模块顺序不符合模板"))
    for marker in ["数据截止时点", "本模块数据日期", "输出为研究参考，不是报价指令。"]:
        if marker not in draft:
            issues.append(_issue("completeness", f"缺少必需声明：{marker}"))
    if draft.count("本模块数据日期") != len(MODULES):
        issues.append(_issue("completeness", "各模块数据日期数量不完整"))
    if metrics is not None:
        numeric = check_numbers(draft, metrics)
        issues.extend(numeric.issues)
    return GateResult("check_completeness", not issues, issues, {"required_modules": list(MODULES)})


def check_timing(draft, metrics, cutoff):
    metrics = _metrics(metrics)
    cutoff_value = datetime.fromisoformat(str(cutoff).replace("Z", "+00:00"))
    referenced = set()
    for line in draft.splitlines():
        key = _metric_for_line(line, metrics)
        if key:
            referenced.add(key)
    issues = []
    for key in sorted(referenced):
        metric = metrics[key]
        available_at = metric.get("available_at")
        if not available_at:
            issues.append(_issue("timing", f"字段缺少 available_at：{key}", details={"field": key}))
            continue
        available = datetime.fromisoformat(available_at.replace("Z", "+00:00"))
        if available > cutoff_value:
            issues.append(_issue("timing", f"字段可得时点晚于信息截止时点：{key}", details={"field": key, "available_at": available_at, "cutoff": str(cutoff)}))
    return GateResult("check_timing", not issues, issues, {"checked_fields": sorted(referenced)})


def check_consistency(candidate, baseline):
    issues = []
    baseline_holdout = {item["case_id"]: item for item in baseline.get("holdout_cases", [])}
    candidate_holdout = {item["case_id"]: item for item in candidate.get("holdout_cases", [])}
    baseline_development = {item["case_id"] for item in baseline.get("development_cases", [])}
    candidate_development = {item["case_id"] for item in candidate.get("development_cases", [])}
    overlap = (set(baseline_holdout) & candidate_development) | (set(candidate_holdout) & baseline_development)
    if overlap:
        issues.append(_issue("consistency", "留出案例与开发案例未分离", details={"overlap": sorted(overlap)}))
    if not baseline_holdout:
        issues.append(_issue("consistency", "缺少历史留出案例"))
    for case_id, base in baseline_holdout.items():
        current = candidate_holdout.get(case_id)
        if current is None:
            issues.append(_issue("consistency", f"候选缺少留出案例：{case_id}", details={"case_id": case_id}))
            continue
        for check, base_passed in base.get("checks", {}).items():
            if base_passed and not current.get("checks", {}).get(check, False):
                issues.append(_issue("consistency", f"留出案例检查劣化：{case_id}/{check}", details={"case_id": case_id, "check": check, "baseline": True, "candidate": False}))
        if "score" in base and _decimal(current.get("score", "不可计算")) is not None:
            if _decimal(current["score"]) < _decimal(base["score"]):
                issues.append(_issue("consistency", f"留出案例得分劣化：{case_id}", details={"case_id": case_id, "baseline": base["score"], "candidate": current["score"]}))
        elif "score" in base:
            issues.append(_issue("consistency", f"候选留出案例得分不可比较：{case_id}", details={"case_id": case_id}))
    return GateResult("check_consistency", not issues, issues, {"holdout_cases": sorted(baseline_holdout)})


def check_identity(reports, required_roles):
    issues = []
    required = set(required_roles)
    present = set()
    for report in reports:
        role = report.get("role")
        if not role:
            issues.append(_issue("identity", "专项报告缺少角色身份", details={"report": report.get("report_id")}))
            continue
        if role in present:
            issues.append(_issue("identity", f"专项报告角色重复：{role}", details={"role": role}))
        present.add(role)
        for key in ["task_id", "report_id", "path", "sha256"]:
            if not report.get(key):
                issues.append(_issue("identity", f"{role} 报告缺少 {key}", details={"role": role, "missing": key}))
        if report.get("self_contained") is not True:
            issues.append(_issue("identity", f"{role} 报告未声明自包含", details={"role": role}))
        path = Path(report.get("path", ""))
        if not path.is_file():
            issues.append(_issue("identity", f"{role} 报告证据文件缺失：{path}", details={"role": role, "path": str(path)}))
        elif report.get("sha256") and hashlib.sha256(path.read_bytes()).hexdigest() != report["sha256"]:
            issues.append(_issue("identity", f"{role} 报告 SHA-256 不一致", details={"role": role, "path": str(path)}))
    for role in sorted(required - present):
        issues.append(_issue("identity", f"缺少必需专项报告：{role}", details={"role": role}))
    return GateResult("check_identity", not issues, issues, {"required_roles": sorted(required), "present_roles": sorted(present)})
