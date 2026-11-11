import calendar
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


DEFAULT_CALENDAR_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "trading_calendar.csv"


@dataclass(frozen=True)
class CalendarEntry:
    day: date
    is_trading_day: bool
    available_at: str


def _parse_day(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError("日期必须是 date 或 YYYY-MM-DD 字符串")


def _parse_timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_calendar(calendar_path):
    path = Path(calendar_path)
    if not path.is_file():
        raise FileNotFoundError(f"交易日历文件缺失：{path}")

    entries = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"date", "is_trading_day", "available_at"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"交易日历必须包含字段：{sorted(required)}")
        for row in reader:
            day = date.fromisoformat(row["date"])
            flag = row["is_trading_day"].strip().lower()
            if flag not in {"0", "1", "true", "false"}:
                raise ValueError(f"无法识别交易日标记：{row['is_trading_day']}")
            if day in entries:
                raise ValueError(f"交易日历存在重复日期：{day.isoformat()}")
            entries[day] = CalendarEntry(
                day=day,
                is_trading_day=flag in {"1", "true"},
                available_at=row["available_at"],
            )
    if not entries:
        raise ValueError(f"交易日历为空：{path}")
    return entries


def _entry(entries, day):
    try:
        return entries[day]
    except KeyError as error:
        raise ValueError(f"交易日历未覆盖日期：{day.isoformat()}") from error


def is_trading_day(day, calendar_path=DEFAULT_CALENDAR_PATH):
    target = _parse_day(day)
    entries = _load_calendar(calendar_path)
    return _entry(entries, target).is_trading_day


def remaining_workdays_in_month(reference_date, calendar_path=DEFAULT_CALENDAR_PATH):
    reference = _parse_day(reference_date)
    entries = _load_calendar(calendar_path)
    _entry(entries, reference)
    last_day = calendar.monthrange(reference.year, reference.month)[1]
    count = 0
    current = reference + timedelta(days=1)
    while current.day <= last_day and current.month == reference.month:
        if _entry(entries, current).is_trading_day:
            count += 1
        current += timedelta(days=1)
    return count


def recent_trading_days(reference_date, count, calendar_path=DEFAULT_CALENDAR_PATH, include_reference=False):
    if not isinstance(count, int) or count <= 0:
        raise ValueError("交易日数量必须是正整数")
    reference = _parse_day(reference_date)
    entries = _load_calendar(calendar_path)
    current = reference if include_reference else reference - timedelta(days=1)
    result = []
    while len(result) < count:
        if _entry(entries, current).is_trading_day:
            result.append(current)
        current -= timedelta(days=1)
    result.reverse()
    return result


def workdays_left_field(reference_date, calendar_path=DEFAULT_CALENDAR_PATH):
    reference = _parse_day(reference_date)
    entries = _load_calendar(calendar_path)
    _entry(entries, reference)
    value = remaining_workdays_in_month(reference, calendar_path)
    last_day = calendar.monthrange(reference.year, reference.month)[1]
    current = reference + timedelta(days=1)
    timestamps = [_entry(entries, reference).available_at]
    while current.day <= last_day and current.month == reference.month:
        timestamps.append(_entry(entries, current).available_at)
        current += timedelta(days=1)
    available_at = max(timestamps, key=_parse_timestamp)
    return {
        "value": value,
        "raw_value": str(value),
        "unit": "个工作日",
        "data_date": reference.isoformat(),
        "available_at": available_at,
        "source_fields": ["trading_calendar"],
    }
