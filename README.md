# 票据市场日评智能体工作流

## 基本信息

- **姓名**：夏小彬
- **学号**：25260660028
- **课程**：金融人工智能编程（MF70047），2026 年秋季
- **项目一句话**：每个交易日早晨，自动生成一份可核验的票据市场日评

**免责声明：输出为研究参考，不是报价指令。**

本项目是名为 `bill-daily` 的 Kimi Code 插件，面向票据交易员与交易台分析师，覆盖票据供给、缺口分析、票据利率、资金面四个日频模块。数值由确定性代码计算并逐项对账，生成方与核验方分离，发布前须经人工批准。

## 阶段进度

| 阶段 | 状态 |
| --- | --- |
| 项目初始化 | 已完成 |
| 任务范围与验收策略定义 | 已完成 |
| 架构设计 | 已完成 |
| 提示词、角色卡、技能与配置 | 已完成 |
| 工作流实现 | 已完成 |
| 端到端测试与证据 | 已完成 |
| 文档与收尾 | 已完成 |
| 提交历史 | 共 9 次有意义的提交，覆盖任务定义、架构设计、提示词与配置、实现、端到端证据、收尾六个阶段 |
| 打包 | 待项目负责人确认后执行 |

## 目录结构说明

| 目录 | 职责 |
| --- | --- |
| `commands/` | 存放插件斜杠命令定义。 |
| `skills/` | 存放插件 Skill 定义。 |
| `agents/` | 存放生成、核验等自定义 Agent 定义。 |
| `references/` | 存放工作流所需的参考资料。 |
| `runtime/dailyflow/` | 存放日评工作流的运行时代码。 |
| `scripts/` | 存放项目辅助脚本。 |
| `hooks/` | 存放仅用于事件留痕的 Kimi Code 生命周期钩子。 |
| `tests/` | 存放项目测试代码。 |
| `tests/fixtures/` | 存放测试使用的固定输入与夹具。 |
| `prompts/` | 存放日评生成与核验提示词模板。 |
| `policies/` | 存放冻结的验收门槛、时点规则与执行边界。 |
| `config/` | 存放工作流与人工批准门配置。 |
| `docs/` | 存放任务定义、任务范围与项目文档。 |
| `data/raw/` | 存放采集或人工录入的原始数据。 |
| `data/snapshots/` | 存放带数据日期、可得时点与口径记录的数据快照。 |
| `evidence/` | 存放来源、计算、对账、核验与审批证据。 |
| `examples/` | 存放示例输入与示例结果。 |
| `output/` | 存放本地生成的日评输出，不纳入版本控制。 |

## 环境配置

### Python 与依赖

- **最低版本：Python 3.10。** 代码使用 dataclasses、f-string 等特性，并在多个文件中使用 `Path.write_text(..., newline=...)`；`newline` 参数由 Python 3.10 引入，因此不能声称 Python 3.9 可直接运行。
- 项目仅使用 Python 标准库，无第三方 pip 依赖；`requirements.txt` 只有说明注释。

```bash
python -m pip install -r requirements.txt
```

该命令无需也不会安装任何第三方包。

### Kimi Code 插件安装

在 Kimi Code 中执行：

```text
/plugins install D:\QT
/reload
```

安装后的入口为：

- `/bill-daily:start`：生成或恢复一个交易日的日评。
- `/bill-daily:evo`：在固定基线上演进工作流。

本项目**不需要任何 API Key**：数值计算由确定性脚本完成，智能体由 Kimi Code 调度。

## 运行说明

以下命令均在项目根目录执行。演示使用合成固定夹具，不访问真实客户数据。

### 跑全部测试

```bash
python -m unittest discover -s tests
```

运行 `tests/` 下全部单元、集成和证据校验测试，结果输出到控制台，不生成运行时报告文件。

### 跑检查脚本

```bash
python scripts/check.py
```

以统一入口运行全部测试，结果输出到控制台；失败时返回非零退出码。

### 跑端到端演示

```bash
python tests/demo_daily_run.py
```

运行 2026-11-11 固定夹具全流程，生成正常日评、时点违规样例、拒绝路径、问题项、审批及演进证据：

- 示例写入 `examples/`
- 证据写入 `evidence/`
- 临时运行状态写入 `output/demo-daily-2026-11-11/`

### 跑断点恢复演示

```bash
python tests/demo_recovery.py
```

先在计算完成后故意中断，再验证恢复时不重复采集和计算。结果写入 `evidence/recovery-demo.md`、`evidence/trace/recovery.jsonl` 和 `evidence/state-snapshots/recovery-verified.json`。

### 跑演进、采纳与回滚演示校验

```bash
python tests/test_evolution.py
```

执行演进函数与演示证据测试，校验固定基线、回归、人工批准、版本采纳和回滚；读取 `evidence/evolution-demo.md`、`evidence/version-registry.jsonl` 等已有证据，不重新生成这些文件。重新生成演进证据请运行 `python tests/demo_daily_run.py`。

### 跑扰动式时点检验

```bash
python scripts/leakage_probe.py
```

加载扰动检验函数；该库脚本本身不生成文件或控制台报告。实际安全与泄露反例断言通过以下命令执行，结果输出到控制台：

```bash
python -m unittest discover -s tests -p "test_leakage_probe.py"
```

### 跑完整日报流程

```bash
python scripts/run_daily.py
```

使用默认固定夹具完成采集、计算、候选生成和两轮核验，最终等待人工批准而不自动发布：

- 运行产物写入 `output/mock-2025-10-02/`
- 归档证据写入 `evidence/mock-2025-10-02/`

可用 `--task-id`、`--case-dir`、`--report-date`、`--cutoff` 和 `--evidence-root` 指定其他合成案例路径。

## 关键文件清单

| 文件或目录 | 是什么 |
| --- | --- |
| `README.md` | 项目身份、环境、运行、资产、贡献与 AI 使用说明。 |
| `AGENTS.md` | 项目目录职责约定。 |
| `docs/01-task-charter.md` | 目标用户、任务产出、输入、验收标准、局限与持久化必要性定义。 |
| `docs/02-architecture.md` | 唯一枢纽拓扑、角色交接、状态机、关卡、恢复与演进架构。 |
| `docs/images/02-architecture-workflow.png` | 实际渲染的工作流拓扑图。 |
| `docs/images/02-architecture-states.png` | 实际渲染的状态机图。 |
| `policies/pit_rules.json` | 逐字段来源、口径、`available_at` 与截止时点可用性规则。 |
| `policies/policy.json` | 冻结的六项验收阈值、修订与执行上限、停止分类和授权边界。 |
| `policies/acceptance-gates.md` | 验收门槛与有界修订策略的可读说明。 |
| `prompts/report_writer_system.md` | ReportWriter 的四模块、数值引用、时点与文风约束。 |
| `prompts/verifier_system.md` | Verifier 的逐数字对账、覆盖检查与问题项要求。 |
| `agents/orchestrator.md` | 唯一枢纽角色卡。 |
| `agents/generator-lead.md` | Generator 负责人及 ReportWriter 绑定角色卡。 |
| `agents/critic-lead.md` | Critic 负责人角色卡。 |
| `agents/evolution-lead.md` | 演进负责人角色卡。 |
| `agents/data-agent.md` | 数据采集专项角色卡。 |
| `agents/timing-agent.md` | 口径与时点判定专项角色卡。 |
| `agents/metrics-agent.md` | 确定性指标计算专项角色卡。 |
| `agents/data-evidence-agent.md` | 数据证据与逐数字对账专项角色卡。 |
| `agents/robustness-agent.md` | 时点与跨模块口径审查专项角色卡。 |
| `agents/execution-agent.md` | 模块、额外数字和格式审查专项角色卡。 |
| `agents/risk-control-agent.md` | 措辞、禁用信息和发布授权审查专项角色卡。 |
| `skills/start/SKILL.md` | 日评生成、核验、修复与人工批准等待流程。 |
| `skills/evo/SKILL.md` | 固定基线、限定演进、回归、登记与回滚流程。 |
| `commands/start.md` | `/bill-daily:start` 的命令入口。 |
| `commands/evo.md` | `/bill-daily:evo` 的命令入口。 |
| `references/schemas.md` | 快照、指标、候选、核验、问题项、状态、版本和批准的 JSON 结构。 |
| `references/policies.md` | 角色契约与权限边界说明。 |
| `references/data-sources.md` | 三源数据字段、发布时点与可用性限制。 |
| `references/template.md` | 四模块日评模板和指标占位符。 |
| `config/workflow.yaml` | 阶段顺序、策略引用、预算和停止规则配置。 |
| `config/approval.yaml` | 人工批准门和分离存储路径配置。 |
| `runtime/dailyflow/states.py` | 状态、迁移、恢复阶段与五类终止结果定义。 |
| `runtime/dailyflow/controller.py` | 证据登记、原子状态写入、路由、恢复和问题项控制。 |
| `runtime/dailyflow/gates.py` | 确定性检查函数及智能体 JSON 命令行入口。 |
| `runtime/dailyflow/evolution.py` | 批准校验、演进范围校验、版本登记与回滚工具。 |
| `scripts/calculator.py` | 纯 Python 指标计算与 JSON 输出。 |
| `scripts/calendar_utils.py` | 显式交易日历读取和工作日计算。 |
| `scripts/collect.py` | 固定夹具快照采集、manifest 与真实接口 TODO。 |
| `scripts/run_daily.py` | 端到端日评编排、轮次目录和证据归档。 |
| `scripts/check.py` | 全量测试统一入口。 |
| `scripts/leakage_probe.py` | 未来数据扰动比较与泄露断言函数。 |
| `scripts/package_final.py` | 包含 `.git/` 完整历史的最终 ZIP 打包与校验工具。 |
| `hooks/audit_event.py` | Bash 后置事件的最小审计留痕 Hook。 |
| `tests/test_calculator.py` | 指标计算和交易日历单元测试。 |
| `tests/test_controller.py` | 控制器、问题项和断点恢复测试。 |
| `tests/test_gates.py` | 数字、时点、身份和留出案例关卡测试。 |
| `tests/test_evolution.py` | 演进函数及端到端证据校验。 |
| `tests/demo_daily_run.py` | 正常、拒绝、审批、采纳与回滚证据生成入口。 |
| `tests/demo_recovery.py` | 计算后中断与零重复计算恢复演示入口。 |
| `examples/2026-11-11-daily-review.md` | 四模块完整正常示例日评。 |
| `examples/2026-11-11-metrics.json` | 正常示例对应的确定性指标结果。 |
| `examples/2026-11-11-snapshot-manifest.json` | 正常示例对应的数据快照 manifest。 |
| `examples/2026-11-11-timing-violation.json` | 可由 `check_timing` 复现 FAIL 的时点违规样例。 |
| `evidence/recovery-demo.md` | 断点恢复全过程与调用次数证据。 |
| `evidence/rejection-demo.md` | 数字、时点和身份三类拒绝路径证据。 |
| `evidence/evolution-demo.md` | 固定基线、采纳与回滚证据。 |
| `evidence/state-snapshots/` | 各阶段及恢复案例的状态快照。 |
| `evidence/trace/` | 关键运行的逐事件 JSONL 轨迹。 |
| `evidence/issues/` | 问题项登记、结转、关闭及拒绝样例。 |
| `evidence/approval-sample/` | 人工批准记录与版本或候选变化后的失效验证。 |
| `evidence/version-registry.jsonl` | 一次采纳和一次回滚的版本历史。 |
| `requirements.txt` | 仅标准库、无 pip 包依赖的声明。 |
| `kimi.plugin.json` | 插件 ID、能力目录、界面信息和审计 Hook 清单。 |

## 代码仓库

代码仓库：https://github.com/xiashuang008/QT

可从 https://github.com/xiashuang008/QT.git 克隆。

仓库包含完整开发历史，最终压缩包内的 `.git/` 目录亦含完整历史，无需访问远程即可审阅全部文件与提交记录。

## 本人贡献说明

这个项目里的代码、角色卡、提示词和测试全部由 Kimi Code 生成。我做的是另一类工作：先把任务想清楚，再逐阶段核对产物是否真的符合设计意图，不符合就退回去重做。

### 我定的设计

**任务是什么。** 选题来自我日常的票据日评工作。原先的做法是每天人工收集票交所、央行、货币网的数据，手算环比同比和缺口，再手写四段话。真正的问题不在写得慢，而在于数字不可复现、结论没有留痕、出了问题没人能独立复核一遍。所以我把流程拆成七段：采集 → 口径判定 → 确定性计算 → 日评生成 → 独立核验 → 人工批准 → 持续监测。

**信息截止时点定在 T-1 日 23:59，四模块统一用 T-1 日数据。** 这条是我在对照自己的日报时定下来的。我手头那份日报的标题写的是交易日 11-11，供给和利率用的是 11-10 的数，资金面用的却是 11-11 的央行操作、SHIBOR 和 DR。但央行操作九点二十才公告，SHIBOR 十一点出，DR 要到十八点——如果日报是早上八点半生成，当天的资金面数据一条都拿不到。所以我把所有模块的口径统一往前推一天，并在系统里加了一道 `check_timing`：任何字段的可得时点晚于信息截止时点，直接判失败。

**阈值和规则在看到任何测试结果之前就冻结。** 六项验收标准、修订回路两轮上限、工具调用与用时上限、停止结果的五种分类，全部先写进 `policies/` 目录。后面写实现时只允许引用，不允许另立标准。这是刻意的——如果阈值是看到结果之后再定的，那它就只是为结果找解释，不是约束。

**按课程第三讲 P25 的拓扑搭角色。** Orchestrator 是唯一枢纽：Generator 做完的候选要先过它才能进 Critic，Critic 的审查结果也不能直接回给 Generator，必须经它生成修复任务包再转发。这两条路径在 Mermaid 图上都标了出来。

**人工批准门。** 数值验收通过不等于可以发布。批准记录要具名、绑定具体版本和候选的 SHA-256、带有效期，而且必须与版本记录分开存放——版本或候选一变，旧批准自动失效。

### 我做的审阅

分阶段推进，每一阶段产出后我核对一遍再放行。有几处是核对时发现缺了、退回去要求补的：

- 阶段 1 结束核对时发现任务书里只写了「各阶段、依赖、触发条件、来源、截止时点」，漏了作业明确要求的**输入清单**，也完全没写**为什么这个任务需要持久化工作流而不是一次性脚本**。这两节补上之后才进阶段 2。
- 阶段 2 的架构说明里没有落地停止结果分类、条件路由四分支、控制器独占写状态这三条讲义要求，也没有扰动式的时点检验。要求补齐并各配测试。
- 拒绝路径的证据要求必须由真实代码跑出来，不接受手写结论。核对的是三种拒绝情形各记录了触发条件、命中的关卡函数、返回的问题项、状态停在哪里、以及 trace 里的路由决策。
- 扰动检验要求做反向验证：人为植入一处未来信息泄露后，该检验必须失败。否则这个检验只是永远返回通过，没有约束力。

### 分工

Kimi Code 负责全部产出物：11 份角色卡、2 份提示词、2 个技能、4 份参考文档、2 个配置文件、12 个 Python 模块、43 项回归测试、以及 `examples/` 和 `evidence/` 下全部演示证据。

我负责上文的全部设计判断，以及分阶段的下达指令、核对、验收和退回修改。

## AI 使用说明

- 本项目的角色卡、提示词、技能、参考文档、实现代码、测试与证据，均由 Kimi Code 依据分步指令生成。
- 分步指令中的以下判断由项目负责人（本人）确定，不由模型决定：任务范围与四模块定义、信息截止时点（T-1 日 23:59）、点时可得性规则、验收标准与阈值、停止结果分类、修订回路轮次上限、人工批准门设计、架构拓扑与角色分工、数据来源范围与禁止使用的信息。
- 阈值与点时规则在看到任何测试结果之前冻结于 `policies/` 目录，实现阶段一律引用该文件，不另立标准。
- 数值一律由确定性代码计算并逐项对账，智能体不自行计算数字。
