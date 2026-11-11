import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.calculator import calculate_case
from scripts.collect import collect_fixture
from scripts.run_daily import InjectedInterruption, run_daily
from runtime.dailyflow.controller import FlowController


def run_demo():
    case_dir = ROOT / "output" / "recovery-demo-case"
    if case_dir.exists():
        shutil.rmtree(case_dir)
    fixtures = ROOT / "tests" / "fixtures"
    first_log = []
    second_log = []
    first_calls = {"calculator": 0}
    second_calls = {"calculator": 0, "collector": 0}

    def first_calculator(payload):
        first_calls["calculator"] += 1
        return calculate_case(payload)

    try:
        run_daily(
            "recovery-demo",
            case_dir,
            fixtures,
            fail_after_calculation=True,
            calculator_fn=first_calculator,
            logger=first_log.append,
        )
    except InjectedInterruption as error:
        first_log.append(f"捕获预期异常：{error}")

    controller = FlowController("recovery-demo", case_dir)
    interrupted_status = controller.read_state()["status"]

    def second_calculator(payload):
        second_calls["calculator"] += 1
        return calculate_case(payload)

    def second_collector(*args):
        second_calls["collector"] += 1
        return collect_fixture(*args)

    result = run_daily(
        "recovery-demo",
        case_dir,
        fixtures,
        calculator_fn=second_calculator,
        collector_fn=second_collector,
        logger=second_log.append,
    )
    final_status = controller.read_state()["status"]
    assert interrupted_status == "calculated"
    assert first_calls["calculator"] == 1
    assert second_calls == {"calculator": 0, "collector": 0}
    assert final_status == "verified"
    assert result["status"] == "verified"

    trace = controller.trace_path.read_text(encoding="utf-8").strip()
    content = [
        "# 断点恢复演示",
        "",
        "本演示仅使用 `tests/fixtures/` 固定数据，不访问网络，不调用 LLM。首次运行在计算完成、日评生成前故意抛出异常；第二次运行从持久化状态恢复。",
        "",
        "## 首次运行：故意中断",
        "",
        "```text",
        *first_log,
        "```",
        "",
        f"中断后状态：`{interrupted_status}`。首次计算器调用次数：`{first_calls['calculator']}`。",
        "",
        "## 第二次运行：从检查点恢复",
        "",
        "```text",
        *second_log,
        "```",
        "",
        "## 恢复结论",
        "",
        "- 恢复入口：`calculated`；下一阶段：`drafted`。",
        "- 第二次采集器调用次数：`0`，未重复采集。",
        "- 第二次计算器调用次数：`0`，未重复计算。",
        "- 候选完成两轮独立核验，最终状态：`verified`，继续等待人工批准，未自动发布。",
        "",
        "## 完整 trace.jsonl",
        "",
        "```json",
        trace,
        "```",
        "",
    ]
    evidence_path = ROOT / "evidence" / "recovery-demo.md"
    evidence_path.write_text("\n".join(content), encoding="utf-8", newline="\n")
    shutil.rmtree(case_dir)
    return evidence_path


if __name__ == "__main__":
    print(run_demo())
