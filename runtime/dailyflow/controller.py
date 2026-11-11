import copy
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from .gates import GateResult
    from .states import FlowState, resume_stage, transition_state
except ImportError:
    from gates import GateResult
    from states import FlowState, resume_stage, transition_state


class EvidenceError(ValueError):
    pass


class FlowController:
    def __init__(self, task_id, case_dir, clock=None):
        self.task_id = task_id
        self.case_dir = Path(case_dir)
        self.case_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.case_dir / "state.json"
        self.issues_path = self.case_dir / "issues.json"
        self.trace_path = self.case_dir / "trace.jsonl"
        self.clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        if not self.state_path.exists():
            self._write_json(self.state_path, {
                "schema_version": "1.0.0",
                "task_id": task_id,
                "request_id": task_id,
                "status": FlowState.CREATED.value,
                "pending_role": "data-agent",
                "revision_round": 0,
                "artifacts": [],
                "unresolved_issue_ids": [],
                "version": "1",
                "consecutive_verification_passes": 0,
                "tool_call_count": 0,
                "total_duration_seconds": 0,
                "updated_at": self._now(),
            })
            self.record_event("request", {"request_id": task_id, "action": "created"})
        if not self.issues_path.exists():
            self._write_json(self.issues_path, {"schema_version": "1.0.0", "task_id": task_id, "issues": [], "updated_at": self._now()})
        if not self.trace_path.exists():
            self._atomic_write(self.trace_path, "")

    def _now(self):
        value = self.clock()
        return value.isoformat() if isinstance(value, datetime) else str(value)

    @staticmethod
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

    def _write_json(self, path, payload):
        self._atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    def read_state(self):
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def read_issues(self):
        return json.loads(self.issues_path.read_text(encoding="utf-8"))["issues"]

    def record_event(self, event, payload):
        entry = {"timestamp": self._now(), "event": event, "task_id": self.task_id, "payload": payload}
        existing = self.trace_path.read_text(encoding="utf-8") if self.trace_path.exists() else ""
        self._atomic_write(self.trace_path, existing + json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

    def register_evidence(self, path, role, kind):
        if not role:
            raise EvidenceError("证据登记缺少角色身份")
        evidence_path = Path(path).resolve()
        if not evidence_path.is_file():
            raise EvidenceError(f"证据文件缺失：{evidence_path}")
        artifact = {
            "kind": kind,
            "path": str(evidence_path),
            "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            "role": role,
            "verified": True,
        }
        state = self.read_state()
        artifacts = [item for item in state["artifacts"] if not (item["kind"] == kind and item["path"] == artifact["path"])]
        artifacts.append(artifact)
        state["artifacts"] = artifacts
        state["updated_at"] = self._now()
        self._write_json(self.state_path, state)
        self.record_event("artifact", artifact)
        return artifact

    def advance(self, target, evidence_paths, role, gate_result):
        if isinstance(gate_result, GateResult):
            gate = gate_result.to_dict()
        elif isinstance(gate_result, dict):
            gate = gate_result
        else:
            gate = {"name": "external_gate", "passed": bool(gate_result), "issues": []}
        for path, kind in evidence_paths:
            self.register_evidence(path, role, kind)
        self.record_event("gate", {"name": gate.get("name"), "passed": bool(gate.get("passed")), "issues": gate.get("issues", [])})
        if not gate.get("passed"):
            self.record_event("route", {"decision": "retry_or_stop", "reason": "关卡未通过，状态不推进", "target": FlowState(target).value})
            return False
        current = FlowState(self.read_state()["status"])
        target = transition_state(current, target, gate_passed=True)
        state = self.read_state()
        state["status"] = target.value
        state["pending_role"] = {
            FlowState.DATA_READY: "timing-agent",
            FlowState.CALCULATED: "generator-lead",
            FlowState.DRAFTED: "critic-lead",
            FlowState.VERIFIED: "票据交易台授权人工批准人",
            FlowState.APPROVED: "orchestrator",
            FlowState.PUBLISHED: None,
        }.get(target)
        state["updated_at"] = self._now()
        self._write_json(self.state_path, state)
        self.record_event("route", {"decision": "advance", "from": current.value, "to": target.value, "role": role})
        return True

    def save_result(self, path, role="orchestrator"):
        artifact = self.register_evidence(path, role, "result")
        state = self.read_state()
        state["result_path"] = artifact["path"]
        state["updated_at"] = self._now()
        self._write_json(self.state_path, state)
        return artifact

    def resume(self):
        state = self.read_state()
        for artifact in state.get("artifacts", []):
            path = Path(artifact["path"])
            if not path.is_file():
                raise EvidenceError(f"恢复所需证据文件缺失：{path}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
                raise EvidenceError(f"恢复所需证据哈希不一致：{path}")
        current = FlowState(state["status"])
        if current == FlowState.PUBLISHED:
            return {"status": "completed", "stage": None, "result_path": state.get("result_path"), "state": state}
        next_stage = resume_stage(current)
        return {
            "status": "waiting_approval" if current == FlowState.VERIFIED else "resumable",
            "stage": next_stage.value if next_stage else None,
            "result_path": state.get("result_path"),
            "state": state,
        }

    def register_issues(self, issues, round_number):
        payload = json.loads(self.issues_path.read_text(encoding="utf-8"))
        existing = {item["id"]: item for item in payload["issues"]}
        for issue in issues:
            item = copy.deepcopy(issue)
            if item["id"] not in existing:
                item["opened_round"] = round_number
                item["status"] = "open"
            else:
                retained = existing[item["id"]]
                retained.update(item)
                retained["status"] = "open"
                item = retained
            existing[item["id"]] = item
            self.record_event("issue", {"action": "registered", "issue_id": item["id"], "round": round_number})
        payload["issues"] = list(existing.values())
        payload["updated_at"] = self._now()
        self._write_json(self.issues_path, payload)
        self._sync_unresolved_issues()

    def carry_forward_issues(self, round_number, addressed_issue_ids, critic_verified_ids, critic_passed, evidence_path=None):
        addressed = set(addressed_issue_ids)
        verified = set(critic_verified_ids)
        evidence = Path(evidence_path).resolve() if evidence_path else None
        payload = json.loads(self.issues_path.read_text(encoding="utf-8"))
        for issue in payload["issues"]:
            if issue["status"] != "open":
                continue
            issue_id = issue["id"]
            was_addressed = issue_id in addressed
            can_close = was_addressed and critic_passed and issue_id in verified and evidence and evidence.is_file()
            history = {
                "round": round_number,
                "addressed": was_addressed,
                "critic_verified": issue_id in verified,
                "closed": bool(can_close),
            }
            issue.setdefault("history", []).append(history)
            if can_close:
                issue["status"] = "resolved"
                issue["resolved_round"] = round_number
                issue["resolution_evidence"] = [str(evidence)]
            else:
                issue["status"] = "open"
                if not was_addressed:
                    issue["last_failure"] = "本轮修复遗漏，继续保持未解决"
            self.record_event("issue", {"action": "carried_forward", **history, "issue_id": issue_id})
        payload["updated_at"] = self._now()
        self._write_json(self.issues_path, payload)
        self._sync_unresolved_issues()
        return payload["issues"]

    def _sync_unresolved_issues(self):
        unresolved = [item["id"] for item in self.read_issues() if item["status"] == "open"]
        state = self.read_state()
        state["unresolved_issue_ids"] = unresolved
        state["updated_at"] = self._now()
        self._write_json(self.state_path, state)

    def increment_revision(self):
        state = self.read_state()
        state["revision_round"] += 1
        state["updated_at"] = self._now()
        self._write_json(self.state_path, state)
        self.record_event("route", {"decision": "repair", "revision_round": state["revision_round"], "route": "Critic -> Orchestrator -> Generator"})
        return state["revision_round"]

    def record_verification_round(self, candidate_sha256, passed):
        state = self.read_state()
        if state.get("verification_candidate_sha256") != candidate_sha256:
            state["consecutive_verification_passes"] = 0
            state["verification_candidate_sha256"] = candidate_sha256
        state["consecutive_verification_passes"] = state.get("consecutive_verification_passes", 0) + 1 if passed else 0
        state["updated_at"] = self._now()
        self._write_json(self.state_path, state)
        self.record_event("gate", {"name": "consecutive_verification", "candidate_sha256": candidate_sha256, "passed": passed, "consecutive_passes": state["consecutive_verification_passes"]})
        return state["consecutive_verification_passes"]
