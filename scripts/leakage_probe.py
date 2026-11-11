import copy
from dataclasses import dataclass, field
from decimal import Decimal


TOLERANCE = Decimal("1e-12")


@dataclass(frozen=True)
class LeakageProbeResult:
    passed: bool
    max_absolute_difference: Decimal
    differences: list = field(default_factory=list)

    def to_dict(self):
        return {
            "passed": self.passed,
            "max_absolute_difference": str(self.max_absolute_difference),
            "differences": self.differences,
        }


def _compare(baseline, perturbed, path, tolerance, differences, maximum):
    if isinstance(baseline, dict) and isinstance(perturbed, dict):
        if set(baseline) != set(perturbed):
            differences.append({"path": path, "reason": "字段集合变化"})
        for key in sorted(set(baseline) & set(perturbed)):
            maximum = _compare(baseline[key], perturbed[key], f"{path}.{key}", tolerance, differences, maximum)
        return maximum
    if isinstance(baseline, (list, tuple)) and isinstance(perturbed, (list, tuple)):
        if len(baseline) != len(perturbed):
            differences.append({"path": path, "reason": "序列长度变化"})
        for index, (left, right) in enumerate(zip(baseline, perturbed)):
            maximum = _compare(left, right, f"{path}[{index}]", tolerance, differences, maximum)
        return maximum
    if isinstance(baseline, (int, float, Decimal)) and not isinstance(baseline, bool) and isinstance(perturbed, (int, float, Decimal)) and not isinstance(perturbed, bool):
        difference = abs(Decimal(str(baseline)) - Decimal(str(perturbed)))
        maximum = max(maximum, difference)
        if difference > tolerance:
            differences.append({"path": path, "baseline": str(baseline), "perturbed": str(perturbed), "absolute_difference": str(difference)})
        return maximum
    if baseline != perturbed:
        differences.append({"path": path, "baseline": baseline, "perturbed": perturbed, "reason": "非数值内容变化"})
    return maximum


def compare_probe_outputs(baseline, perturbed, tolerance=TOLERANCE):
    tolerance = Decimal(str(tolerance))
    if tolerance < 0:
        raise ValueError("容差不得为负数")
    differences = []
    maximum = _compare(baseline, perturbed, "output", tolerance, differences, Decimal(0))
    return LeakageProbeResult(not differences, maximum, differences)


def run_leakage_probe(data, cutoff, signal_fn, prediction_fn, perturb_fn):
    baseline_data = copy.deepcopy(data)
    perturbed_data = perturb_fn(copy.deepcopy(data), cutoff)
    baseline = {
        "signals": signal_fn(copy.deepcopy(baseline_data), cutoff),
        "predictions": prediction_fn(copy.deepcopy(baseline_data), cutoff) if prediction_fn else None,
    }
    perturbed = {
        "signals": signal_fn(copy.deepcopy(perturbed_data), cutoff),
        "predictions": prediction_fn(copy.deepcopy(perturbed_data), cutoff) if prediction_fn else None,
    }
    return compare_probe_outputs(baseline, perturbed)


def assert_no_leakage(result):
    if not result.passed:
        raise AssertionError(f"检测到未来信息泄露：{result.to_dict()}")
