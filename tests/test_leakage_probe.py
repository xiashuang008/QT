import unittest
from decimal import Decimal

from scripts.leakage_probe import assert_no_leakage, run_leakage_probe


DATA = [
    {"data_date": "2025-09-29", "value": 10},
    {"data_date": "2025-09-30", "value": 20},
    {"data_date": "2025-10-01", "value": 30},
]
CUTOFF = "2025-09-30"


def perturb_future(data, cutoff):
    for row in data:
        if row["data_date"] > cutoff:
            row["value"] = 999999
    return data


def safe_signal(data, cutoff):
    return sum(row["value"] for row in data if row["data_date"] <= cutoff)


def safe_prediction(data, cutoff):
    return safe_signal(data, cutoff) * 2


def leaky_signal(data, cutoff):
    return sum(row["value"] for row in data)


class LeakageProbeTests(unittest.TestCase):
    def test_future_perturbation_does_not_change_pit_outputs(self):
        result = run_leakage_probe(DATA, CUTOFF, safe_signal, safe_prediction, perturb_future)

        self.assertTrue(result.passed)
        self.assertEqual(result.max_absolute_difference, Decimal(0))
        assert_no_leakage(result)

    def test_probe_fails_when_future_information_leaks(self):
        result = run_leakage_probe(DATA, CUTOFF, leaky_signal, safe_prediction, perturb_future)

        self.assertFalse(result.passed)
        self.assertGreater(result.max_absolute_difference, Decimal("1e-12"))
        self.assertTrue(any("signals" in item["path"] for item in result.differences))
        with self.assertRaisesRegex(AssertionError, "未来信息泄露"):
            assert_no_leakage(result)


if __name__ == "__main__":
    unittest.main()
