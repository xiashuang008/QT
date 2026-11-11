import copy
import unittest
from datetime import date
from pathlib import Path

from scripts.calculator import (
    build_metrics_result,
    compute_funding_metrics,
    compute_gap_metrics,
    compute_rate_metrics,
    compute_supply_metrics,
)
from scripts.calendar_utils import (
    is_trading_day,
    recent_trading_days,
    remaining_workdays_in_month,
)


ROOT = Path(__file__).resolve().parents[1]
CALENDAR = ROOT / "tests" / "fixtures" / "trading_calendar.csv"


def field(value, unit="亿元", data_date="2026-09-29", available_at="2026-09-30T09:00:00+08:00"):
    return {
        "value": value,
        "raw_value": str(value),
        "unit": unit,
        "data_date": data_date,
        "available_at": available_at,
    }


class CalculatorTests(unittest.TestCase):
    def test_supply_mom_yoy_and_acceptance_discount_ratio(self):
        today = {
            "acceptance": field(120),
            "discount": field(60),
            "trading": field(30),
        }
        yesterday = {
            "acceptance": field(100, data_date="2026-09-28", available_at="2026-09-29T09:00:00+08:00"),
            "discount": field(50, data_date="2026-09-28", available_at="2026-09-29T09:00:00+08:00"),
            "trading": field(25, data_date="2026-09-28", available_at="2026-09-29T09:00:00+08:00"),
        }
        last_year = {
            "acceptance": field(80, data_date="2025-09-29", available_at="2025-09-30T09:00:00+08:00"),
            "discount": field(40, data_date="2025-09-29", available_at="2025-09-30T09:00:00+08:00"),
            "trading": field(20, data_date="2025-09-29", available_at="2025-09-30T09:00:00+08:00"),
        }

        result = compute_supply_metrics(today, yesterday, last_year)

        self.assertEqual(result["acceptance_mom"]["raw_value"], "20")
        self.assertEqual(result["discount_mom"]["raw_value"], "20")
        self.assertEqual(result["trading_yoy"]["raw_value"], "50")
        self.assertEqual(result["acceptance_yoy"]["raw_value"], "50")
        self.assertEqual(result["acceptance_discount_ratio"]["raw_value"], "50")
        self.assertEqual(result["acceptance_discount_ratio"]["unit"], "%")
        self.assertEqual(
            result["acceptance_mom"]["available_at"],
            "2026-09-30T09:00:00+08:00",
        )

    def test_zero_denominator_returns_unavailable(self):
        today = {"acceptance": field(0), "discount": field(60), "trading": field(30)}
        yesterday = {"acceptance": field(0), "discount": field(50), "trading": field(25)}
        last_year = {"acceptance": field(80), "discount": field(40), "trading": field(20)}

        result = compute_supply_metrics(today, yesterday, last_year)

        self.assertIsNone(result["acceptance_mom"]["value"])
        self.assertEqual(result["acceptance_mom"]["raw_value"], "不可计算")
        self.assertEqual(result["acceptance_mom"]["calculation_status"], "unavailable")
        self.assertEqual(result["acceptance_discount_ratio"]["value"], None)
        self.assertIn("分母为零", result["acceptance_discount_ratio"]["reason"])

    def test_gap_and_daily_required_amount(self):
        result = compute_gap_metrics(
            field(1000),
            field(400),
            field(5, unit="个工作日"),
            field(80),
        )

        self.assertEqual(result["discount_gap"]["raw_value"], "600")
        self.assertEqual(result["daily_required_amount"]["raw_value"], "120")
        self.assertEqual(result["recent5_daily_avg"]["raw_value"], "80")

    def test_zero_workdays_returns_unavailable(self):
        result = compute_gap_metrics(
            field(1000),
            field(400),
            field(0, unit="个工作日"),
            field(80),
        )

        self.assertIsNone(result["daily_required_amount"]["value"])
        self.assertEqual(result["daily_required_amount"]["calculation_status"], "unavailable")

    def test_rate_spread(self):
        rates = {
            "3M": {
                "cross_year": field("1.50", unit="%"),
                "regular": field("1.20", unit="%"),
            }
        }

        result = compute_rate_metrics(rates, cross_year_flag=True)

        self.assertEqual(result["cross_year_bill_rate"]["raw_value"], "1.50")
        self.assertEqual(result["regular_bill_rate"]["raw_value"], "1.20")
        self.assertEqual(result["cross_year_regular_spread"]["raw_value"], "0.30")
        self.assertEqual(result["cross_year_regular_spread"]["unit"], "百分点")

    def test_funding_net_injection_and_spreads(self):
        result = compute_funding_metrics(
            {"injection": field(1000), "maturity": field(700)},
            field("1.30", unit="%"),
            field("1.40", unit="%"),
            field("1.80", unit="%"),
            field("1.90", unit="%"),
        )

        self.assertEqual(result["omo_net_injection"]["raw_value"], "300")
        self.assertEqual(result["omo_net_injection"]["operation"], "net_injection")
        self.assertEqual(result["dr001_shibor_spread"]["raw_value"], "0.10")
        self.assertEqual(result["dr007_shibor_spread"]["raw_value"], "0.50")
        self.assertEqual(result["r007"]["raw_value"], "1.90")

    def test_funding_net_withdrawal(self):
        result = compute_funding_metrics(
            {"injection": field(500), "maturity": field(800)},
            field("1.30", unit="%"),
            field("1.40", unit="%"),
            field("1.80", unit="%"),
            field("1.90", unit="%"),
        )

        self.assertEqual(result["omo_net_injection"]["raw_value"], "-300")
        self.assertEqual(result["omo_net_injection"]["operation"], "net_withdrawal")
        self.assertEqual(result["omo_net_injection"]["display_name"], "公开市场操作净回笼")

    def test_same_input_returns_identical_output(self):
        today = {"acceptance": field(120), "discount": field(60), "trading": field(30)}
        yesterday = {"acceptance": field(100), "discount": field(50), "trading": field(25)}
        last_year = {"acceptance": field(80), "discount": field(40), "trading": field(20)}
        original = copy.deepcopy((today, yesterday, last_year))

        first = compute_supply_metrics(today, yesterday, last_year)
        second = compute_supply_metrics(today, yesterday, last_year)

        self.assertEqual(first, second)
        self.assertEqual((today, yesterday, last_year), original)

    def test_metrics_result_matches_reference_structure(self):
        metrics = compute_gap_metrics(field(1000), field(400), field(5, unit="个工作日"), field(80))

        result = build_metrics_result(
            task_id="task-1",
            created_at="2026-09-30T10:00:00+08:00",
            metrics=metrics,
            calculator_path=str(ROOT / "scripts" / "calculator.py"),
            input_sha256="a" * 64,
        )

        for key in ["schema_version", "task_id", "result_id", "calculator_path", "input_sha256", "created_at", "metrics"]:
            self.assertIn(key, result)
        for metric in result["metrics"].values():
            for key in ["display_name", "value", "raw_value", "unit", "data_date", "available_at"]:
                self.assertIn(key, metric)


class CalendarTests(unittest.TestCase):
    def test_remaining_workdays_crosses_holidays(self):
        self.assertEqual(remaining_workdays_in_month("2025-10-01", CALENDAR), 18)
        self.assertFalse(is_trading_day("2025-10-01", CALENDAR))
        self.assertTrue(is_trading_day("2025-10-11", CALENDAR))

    def test_recent_trading_days_uses_calendar(self):
        self.assertEqual(
            recent_trading_days("2025-10-10", 3, CALENDAR),
            [date(2025, 9, 29), date(2025, 9, 30), date(2025, 10, 9)],
        )

    def test_missing_calendar_fails(self):
        with self.assertRaises(FileNotFoundError):
            remaining_workdays_in_month("2025-09-30", ROOT / "tests" / "fixtures" / "missing.csv")


if __name__ == "__main__":
    unittest.main()
