# 断点恢复演示

本演示仅使用 `tests/fixtures/` 固定数据，不访问网络，不调用 LLM。首次运行在计算完成、日评生成前故意抛出异常；第二次运行从持久化状态恢复。

## 首次运行：故意中断

```text
task_id=recovery-demo；当前状态=created；恢复阶段=data_ready
开始采集固定夹具
采集完成，状态=data_ready
开始确定性计算
计算完成，状态=calculated
故意中断：计算完成、日评生成前
捕获预期异常：计算完成、日评生成前的故意中断
```

中断后状态：`calculated`。首次计算器调用次数：`1`。

## 第二次运行：从检查点恢复

```text
task_id=recovery-demo；当前状态=calculated；恢复阶段=drafted
恢复或进入 drafted：跳过已完成的采集与计算
候选日评完成，状态=drafted
Critic 第 1 轮独立核验，使用新上下文
第 1 轮核验通过；同一候选连续通过=1
Critic 第 2 轮独立核验，使用新上下文
第 2 轮核验通过；同一候选连续通过=2
核验完成，状态=verified
停止自动执行，等待具名人工 approve；未获得发布授权
```

## 恢复结论

- 恢复入口：`calculated`；下一阶段：`drafted`。
- 第二次采集器调用次数：`0`，未重复采集。
- 第二次计算器调用次数：`0`，未重复计算。
- 候选完成两轮独立核验，最终状态：`verified`，继续等待人工批准，未自动发布。

## 完整 trace.jsonl

```json
{"event": "request", "payload": {"action": "created", "request_id": "recovery-demo"}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:51.968610+00:00"}
{"event": "artifact", "payload": {"kind": "snapshot_manifest", "path": "D:\\QT\\output\\recovery-demo-case\\snapshots\\2025-10-02\\manifest.json", "role": "data-agent", "sha256": "8ff7878281c075c8d000683cfe80e6b37a6fce9a5c0e30b914206bb8e3e69dc2", "verified": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:51.985902+00:00"}
{"event": "gate", "payload": {"issues": [], "name": "check_freshness", "passed": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:51.989044+00:00"}
{"event": "route", "payload": {"decision": "advance", "from": "created", "role": "data-agent", "to": "data_ready"}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:51.995437+00:00"}
{"event": "artifact", "payload": {"kind": "metrics", "path": "D:\\QT\\output\\recovery-demo-case\\metrics.json", "role": "metrics-agent", "sha256": "a9d5f1b25760759e0e0b8e5db0c4af42fe1ad710fb3ca39584e8e66f8bd7edea", "verified": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:52.004277+00:00"}
{"event": "gate", "payload": {"issues": [], "name": "calculator_completed", "passed": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:52.006469+00:00"}
{"event": "route", "payload": {"decision": "advance", "from": "data_ready", "role": "metrics-agent", "to": "calculated"}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:52.010963+00:00"}
{"event": "route", "payload": {"decision": "interrupted", "reason": "计算完成、日评生成前的故意中断"}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:52.012858+00:00"}
{"event": "artifact", "payload": {"kind": "candidate", "path": "D:\\QT\\output\\recovery-demo-case\\candidate.md", "role": "generator-lead", "sha256": "4887b80a017dc45fd752b503927b9d6ad706d0c6a970c53f0a12119c4b080efa", "verified": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:52.021386+00:00"}
{"event": "gate", "payload": {"issues": [], "name": "draft_gates", "passed": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:52.023806+00:00"}
{"event": "route", "payload": {"decision": "advance", "from": "calculated", "role": "generator-lead", "to": "drafted"}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:52.028313+00:00"}
{"event": "gate", "payload": {"candidate_sha256": "4887b80a017dc45fd752b503927b9d6ad706d0c6a970c53f0a12119c4b080efa", "consecutive_passes": 1, "name": "consecutive_verification", "passed": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:52.048202+00:00"}
{"event": "gate", "payload": {"candidate_sha256": "4887b80a017dc45fd752b503927b9d6ad706d0c6a970c53f0a12119c4b080efa", "consecutive_passes": 2, "name": "consecutive_verification", "passed": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:52.073278+00:00"}
{"event": "artifact", "payload": {"kind": "verification", "path": "D:\\QT\\output\\recovery-demo-case\\verification.json", "role": "critic-lead", "sha256": "1b5fc6f3c2bf0d0d4d35e1fb7a8c016e3fa019c94dbc918662ffe6773bfc653e", "verified": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:52.080023+00:00"}
{"event": "gate", "payload": {"issues": [], "name": "verification_acceptance", "passed": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:52.082424+00:00"}
{"event": "route", "payload": {"decision": "advance", "from": "drafted", "role": "critic-lead", "to": "verified"}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:52.087504+00:00"}
{"event": "artifact", "payload": {"kind": "result", "path": "D:\\QT\\output\\recovery-demo-case\\result.json", "role": "orchestrator", "sha256": "b8562e9b13cd0526c1f6b6659f4342646638189614133e4f0d08e566fef7a95e", "verified": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T12:45:52.097382+00:00"}
```
