# 断点恢复演示

本演示仅使用 `tests/fixtures/` 固定数据，不访问网络，不调用 LLM。首次运行在计算完成、日评生成前故意抛出异常；第二次运行从持久化状态恢复。

## 首次运行：故意中断

```text
task_id=recovery-demo；当前状态=created；恢复阶段=data_ready
开始采集固定夹具
采集与口径判定完成，状态=data_ready
由指标岗通过 Bash 等价入口调用确定性计算器
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
{"event": "request", "payload": {"action": "created", "request_id": "recovery-demo"}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.565974+00:00"}
{"event": "artifact", "payload": {"kind": "snapshot_manifest", "path": "D:\\QT\\output\\recovery-demo-case\\snapshots\\2025-10-02\\manifest.json", "role": "data-agent", "sha256": "8ff7878281c075c8d000683cfe80e6b37a6fce9a5c0e30b914206bb8e3e69dc2", "verified": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.597279+00:00"}
{"event": "artifact", "payload": {"kind": "data_report", "path": "D:\\QT\\output\\recovery-demo-case\\rounds\\round-001\\generator\\data-agent.json", "role": "data-agent", "sha256": "846d607528094d4030b17c0881428c43fbf898511a558b9ae809a4b5b5969bca", "verified": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.603818+00:00"}
{"event": "gate", "payload": {"issues": [], "name": "check_freshness", "passed": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.607013+00:00"}
{"event": "route", "payload": {"decision": "advance", "from": "created", "role": "data-agent", "to": "data_ready"}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.615254+00:00"}
{"event": "artifact", "payload": {"kind": "timing_report", "path": "D:\\QT\\output\\recovery-demo-case\\rounds\\round-001\\generator\\timing-agent.json", "role": "timing-agent", "sha256": "7dad00004101aa1a31d981f1576917e4194aa173fb1da490d21c167c74010319", "verified": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.625198+00:00"}
{"event": "artifact", "payload": {"kind": "metrics", "path": "D:\\QT\\output\\recovery-demo-case\\rounds\\round-001\\generator\\metrics.json", "role": "metrics-agent", "sha256": "a9d5f1b25760759e0e0b8e5db0c4af42fe1ad710fb3ca39584e8e66f8bd7edea", "verified": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.640857+00:00"}
{"event": "artifact", "payload": {"kind": "metrics_report", "path": "D:\\QT\\output\\recovery-demo-case\\rounds\\round-001\\generator\\metrics-agent.json", "role": "metrics-agent", "sha256": "a7194f571161a27a78d58751b8d4401d9469c8534ab0832ce1961571ccf287a8", "verified": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.646527+00:00"}
{"event": "gate", "payload": {"issues": [], "name": "calculator_completed", "passed": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.649295+00:00"}
{"event": "route", "payload": {"decision": "advance", "from": "data_ready", "role": "metrics-agent", "to": "calculated"}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.658203+00:00"}
{"event": "route", "payload": {"decision": "interrupted", "reason": "计算完成、日评生成前的故意中断"}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.660674+00:00"}
{"event": "artifact", "payload": {"kind": "candidate", "path": "D:\\QT\\output\\recovery-demo-case\\rounds\\round-001\\generator\\candidate.md", "role": "generator-lead", "sha256": "4887b80a017dc45fd752b503927b9d6ad706d0c6a970c53f0a12119c4b080efa", "verified": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.673509+00:00"}
{"event": "gate", "payload": {"issues": [], "name": "draft_gates", "passed": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.676446+00:00"}
{"event": "route", "payload": {"decision": "advance", "from": "calculated", "role": "generator-lead", "to": "drafted"}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.685305+00:00"}
{"event": "gate", "payload": {"candidate_sha256": "4887b80a017dc45fd752b503927b9d6ad706d0c6a970c53f0a12119c4b080efa", "consecutive_passes": 1, "name": "consecutive_verification", "passed": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.712332+00:00"}
{"event": "route", "payload": {"decision": "继续", "reason": "继续同一候选的下一轮独立核验", "round": 1}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.722774+00:00"}
{"event": "gate", "payload": {"candidate_sha256": "4887b80a017dc45fd752b503927b9d6ad706d0c6a970c53f0a12119c4b080efa", "consecutive_passes": 2, "name": "consecutive_verification", "passed": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.773119+00:00"}
{"event": "route", "payload": {"decision": "结束", "reason": "验收通过，等待人工批准", "round": 2}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.790102+00:00"}
{"event": "artifact", "payload": {"kind": "verification", "path": "D:\\QT\\output\\recovery-demo-case\\rounds\\round-002\\critic\\verification.json", "role": "critic-lead", "sha256": "17acaf8e1650823fb2652583a1d8a5d6aea2b3e2dc6bd77a512535bc4613b7d0", "verified": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.797634+00:00"}
{"event": "gate", "payload": {"issues": [], "name": "verification_acceptance", "passed": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.800743+00:00"}
{"event": "route", "payload": {"decision": "advance", "from": "drafted", "role": "critic-lead", "to": "verified"}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.813031+00:00"}
{"event": "artifact", "payload": {"kind": "result", "path": "D:\\QT\\output\\recovery-demo-case\\result.json", "role": "orchestrator", "sha256": "5f5a28d7e30a1bd1d333472fcddb42960a28389ee6546c42661f938c882dc76d", "verified": true}, "task_id": "recovery-demo", "timestamp": "2026-11-11T15:59:49.825692+00:00"}
```
