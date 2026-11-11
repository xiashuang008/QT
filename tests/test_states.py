import unittest

from runtime.dailyflow.states import FlowState, TransitionError, assess_state, transition_state


class StateTests(unittest.TestCase):
    def test_illegal_transition_is_rejected(self):
        with self.assertRaisesRegex(TransitionError, "非法迁移"):
            transition_state(FlowState.CREATED, FlowState.CALCULATED, gate_passed=True)

    def test_manual_approval_is_rejected(self):
        with self.assertRaisesRegex(TransitionError, "手工推进被拒绝"):
            transition_state(FlowState.VERIFIED, FlowState.APPROVED, gate_passed=True, manual=True)

    def test_protected_state_requires_gate(self):
        with self.assertRaisesRegex(TransitionError, "仅能由关卡判定"):
            transition_state(FlowState.VERIFIED, FlowState.APPROVED, gate_passed=False)
        self.assertEqual(
            transition_state(FlowState.VERIFIED, FlowState.APPROVED, gate_passed=True),
            FlowState.APPROVED,
        )

    def test_four_state_assessments(self):
        completed = assess_state(output_verified=True)
        pending = assess_state(request_sent=True)
        uncertain = assess_state()
        self.assertEqual((completed.category, completed.reason), ("已完成", "输出已核验"))
        self.assertEqual((pending.category, pending.reason), ("待处理", "请求已发出"))
        self.assertEqual((uncertain.category, uncertain.reason), ("不确定", "完成情况未知"))
        self.assertEqual(uncertain.next_step, "先检查再恢复运行")


if __name__ == "__main__":
    unittest.main()
