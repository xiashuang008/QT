from dataclasses import dataclass
from enum import Enum


class FlowState(str, Enum):
    CREATED = "created"
    DATA_READY = "data_ready"
    CALCULATED = "calculated"
    DRAFTED = "drafted"
    VERIFIED = "verified"
    APPROVED = "approved"
    PUBLISHED = "published"


STATE_ORDER = (
    FlowState.CREATED,
    FlowState.DATA_READY,
    FlowState.CALCULATED,
    FlowState.DRAFTED,
    FlowState.VERIFIED,
    FlowState.APPROVED,
    FlowState.PUBLISHED,
)
PROTECTED_STATES = {FlowState.APPROVED, FlowState.PUBLISHED}


class TransitionError(ValueError):
    pass


@dataclass(frozen=True)
class StateAssessment:
    category: str
    completed: bool
    pending: bool
    uncertain: bool
    next_step: str
    reason: str


def assess_state(output_verified=False, request_sent=False):
    if output_verified:
        return StateAssessment(
            category="已完成",
            completed=True,
            pending=False,
            uncertain=False,
            next_step="返回已保存结果",
            reason="输出已核验",
        )
    if request_sent:
        return StateAssessment(
            category="待处理",
            completed=False,
            pending=True,
            uncertain=False,
            next_step="先检查再恢复运行",
            reason="请求已发出",
        )
    return StateAssessment(
        category="不确定",
        completed=False,
        pending=False,
        uncertain=True,
        next_step="先检查再恢复运行",
        reason="完成情况未知",
    )


def transition_state(current, target, gate_passed=False, manual=False):
    current = FlowState(current)
    target = FlowState(target)
    if manual and target in PROTECTED_STATES:
        raise TransitionError(f"{target.value} 仅能由关卡判定，手工推进被拒绝")
    try:
        current_index = STATE_ORDER.index(current)
    except ValueError as error:
        raise TransitionError(f"未知当前状态：{current}") from error
    if target not in STATE_ORDER:
        raise TransitionError(f"未知目标状态：{target}")
    if target != STATE_ORDER[current_index + 1]:
        raise TransitionError(f"非法迁移：{current.value} → {target.value}")
    if target in PROTECTED_STATES and not gate_passed:
        raise TransitionError(f"{target.value} 仅能由关卡判定，未提供通过的关卡结果")
    return target


def resume_stage(current):
    current = FlowState(current)
    if current == FlowState.PUBLISHED:
        return None
    return STATE_ORDER[STATE_ORDER.index(current) + 1]
