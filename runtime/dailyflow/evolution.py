import json
import os
import tempfile
from datetime import datetime
from pathlib import Path


REQUIRED_APPROVAL_FIELDS = ("approval_id", "task_id", "version", "candidate_sha256", "approver_name", "approver_role", "conclusion", "approved_at", "expires_at")


def validate_approval(record, version, candidate_sha256, at_time):
    reasons = []
    for key in REQUIRED_APPROVAL_FIELDS:
        if not record.get(key):
            reasons.append(f"批准记录缺少 {key}")
    if record.get("version") != version:
        reasons.append("批准版本不匹配")
    if record.get("candidate_sha256") != candidate_sha256:
        reasons.append("批准候选 SHA-256 不匹配")
    if record.get("conclusion") != "approve":
        reasons.append("批准结论不是 approve")
    current = datetime.fromisoformat(str(at_time).replace("Z", "+00:00"))
    if record.get("approved_at") and datetime.fromisoformat(record["approved_at"].replace("Z", "+00:00")) > current:
        reasons.append("批准时间晚于当前时点")
    if record.get("expires_at") and datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00")) <= current:
        reasons.append("批准已过期")
    return {"valid": not reasons, "reasons": reasons}


def validate_evolution_proposal(proposal):
    reasons = []
    allowed_prefixes = ("prompts/", "skills/", "context/")
    forbidden_prefixes = ("policies/", "runtime/", "config/")
    for path in proposal.get("allowed_changes", []):
        if not path.startswith(allowed_prefixes):
            reasons.append(f"改动超出提示词、上下文或技能范围：{path}")
        if path.startswith(forbidden_prefixes):
            reasons.append(f"禁止修改验收或控制器资产：{path}")
    if not proposal.get("allowed_changes"):
        reasons.append("改动提案没有明确限定路径")
    if proposal.get("acceptance_standard") != "unchanged" or proposal.get("lower_acceptance", False):
        reasons.append("改动提案不得降低验收标准")
    return {"passed": not reasons, "reasons": reasons}


def _atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def append_version_record(registry_path, record):
    path = Path(registry_path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    _atomic_write(path, existing + json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def rollback_version(registry_path, current_version, target_version, reason, rolled_back_at, metadata=None):
    path = Path(registry_path)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
    versions = {record.get("version") for record in records}
    if current_version not in versions or target_version not in versions:
        raise ValueError("当前版本或回滚目标未登记，禁止回滚")
    event = {
        "schema_version": "1.0.0",
        "event": "rollback",
        "version": target_version,
        "from_version": current_version,
        "target_version": target_version,
        "reason": reason,
        "rolled_back_at": rolled_back_at,
        "requires_new_case_verification": True,
    }
    if metadata:
        event.update(metadata)
    append_version_record(path, event)
    return event
