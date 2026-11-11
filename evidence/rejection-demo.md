# 拒绝路径演示

本文件由 `tests/demo_daily_run.py` 调用真实关卡与控制器生成，全部使用合成数据。

## numbers

- 触发条件：正文贴现量由 75 改为 80，指标结果仍为 75
- 命中的关卡：`check_numbers`，返回 `FAIL`。
- 返回问题项：`numbers-19148f59f6e5`；正文数值与指标结果不一致：80
- 问题明细：`{"actual": "80", "expected": "75", "difference": "5", "metric": "discount_amount", "location": "- 贴现量：80 亿元"}`
- 状态停留：`created` → `created`，未推进。
- trace 路由决策：`repair`；检查未通过，由当前角色修复，不推进下游

## timing

- 触发条件：DR001 available_at 改为 2026-11-11T18:00:00+08:00
- 命中的关卡：`check_timing`，返回 `FAIL`。
- 返回问题项：`timing-1857a380acfc`；字段可得时点晚于信息截止时点：dr001
- 问题明细：`{"field": "dr001", "available_at": "2026-11-11T18:00:00+08:00", "cutoff": "2026-11-10T23:59:00+08:00"}`
- 状态停留：`created` → `created`，未推进。
- trace 路由决策：`repair`；检查未通过，由当前角色修复，不推进下游

## identity

- 触发条件：专项报告元数据缺少 role
- 命中的关卡：`check_identity`，返回 `FAIL`。
- 返回问题项：`identity-f84e0b5a9837`；专项报告缺少角色身份
- 问题明细：`{"report": "missing-role-report"}`
- 状态停留：`created` → `created`，未推进。
- trace 路由决策：`repair`；检查未通过，由当前角色修复，不推进下游
