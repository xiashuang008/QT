# 演进、采纳与回滚演示

本文件由真实回归关卡、批准校验和版本注册函数生成，使用固定基线与合成数据。

## 固定基线与限定范围改动

- 基线版本：`v2026.11.11.1`；候选版本：`v2026.11.11.2`；候选 SHA-256：`e8495662f383ae83fa015a1226692bd34277f515a75a16aec8cd3c38a89733b4`。
- 允许改动仅限 `prompts/report_writer_system.md` 与 `skills/start/SKILL.md`。
- 提案明确不修改验收规则、阈值或控制器代码，且 `lower_acceptance=false`。

## 比较、回归与 Critic 审查

- `check_consistency`：PASS；留出案例与开发案例分离。
- Critic 代码关卡：check_numbers=PASS, check_completeness=PASS, check_timing=PASS, check_wording=PASS。
- 人工批准校验：`{"valid": true, "reasons": []}`。

## 采纳与回滚

- 采纳：`v2026.11.11.2` 经人工批准后写入版本注册表并标记为启用。
- 回滚：`v2026.11.11.2` → `v2026.11.11.1`；新旧版本证据均保留在 `evidence/evolution/versions/`。
- 回滚记录明确 `requires_new_case_verification=true`，回滚后的行为必须在新案例中重新核验，不复用旧批准。
