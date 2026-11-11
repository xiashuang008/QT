import argparse
import copy
import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

try:
    from .calendar_utils import workdays_left_field
except ImportError:
    from calendar_utils import workdays_left_field


SCHEMA_VERSION = "1.0.0"


def _raw_value(field):
    if not isinstance(field, dict) or "value" not in field:
        raise ValueError("指标输入必须是包含 value 的对象")
    for key in ["unit", "data_date", "available_at"]:
        if key not in field:
            raise ValueError(f"指标输入缺少 {key}")
    return str(field.get("raw_value", field["value"]))


def _decimal(field):
    raw = _raw_value(field)
    try:
        return Decimal(raw)
    except InvalidOperation as error:
        raise ValueError(f"无法解析数值：{raw}") from error


def _parse_timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("available_at 必须包含时区")
    return parsed


def _latest_available_at(fields):
    values = [field["available_at"] for field in fields]
    if not values or any(not value for value in values):
        raise ValueError("每个输入都必须提供 available_at")
    return max(values, key=_parse_timestamp)


def _json_number(value):
    if value is None:
        return None
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _format_decimal(value, precision=None):
    if precision is not None:
        quantum = Decimal(1).scaleb(-precision)
        return format(value.quantize(quantum), "f")
    normalized = format(value.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return "0" if normalized in {"", "-0"} else normalized


def _precision(field):
    raw = _raw_value(field)
    if "." not in raw:
        return 0
    return len(raw.split(".", 1)[1])


def _metric(display_name, value, raw_value, unit, data_date, available_at, status="computed", reason=None, base_period=None, source_fields=None, extra=None):
    result = {
        "display_name": display_name,
        "value": _json_number(value),
        "raw_value": raw_value,
        "unit": unit,
        "data_date": data_date,
        "available_at": available_at,
        "calculation_status": status,
        "source_fields": source_fields or [],
    }
    if reason is not None:
        result["reason"] = reason
    if base_period is not None:
        result["base_period"] = base_period
    if extra:
        result.update(extra)
    return result


def _reference_metric(field, display_name):
    value = _decimal(field)
    return _metric(
        display_name=display_name,
        value=value,
        raw_value=_raw_value(field),
        unit=field["unit"],
        data_date=field["data_date"],
        available_at=field["available_at"],
        status="reference",
        source_fields=field.get("source_fields", []),
    )


def _unavailable(display_name, unit, fields, data_date, reason, base_period=None, source_fields=None):
    return _metric(
        display_name=display_name,
        value=None,
        raw_value="不可计算",
        unit=unit,
        data_date=data_date,
        available_at=_latest_available_at(fields),
        status="unavailable",
        reason=reason,
        base_period=base_period,
        source_fields=source_fields,
    )


def _change_metric(current, base, display_name, source_name):
    sources = [f"{source_name}:current", f"{source_name}:base"]
    base_value = _decimal(base)
    if base_value == 0:
        return _unavailable(display_name, "%", [current, base], current["data_date"], "分母为零", base["data_date"], sources)
    value = (_decimal(current) - base_value) / base_value * Decimal(100)
    return _metric(
        display_name,
        value,
        _format_decimal(value),
        "%",
        current["data_date"],
        _latest_available_at([current, base]),
        base_period=base["data_date"],
        source_fields=sources,
    )


def _ratio_metric(numerator, denominator, display_name, multiplier=Decimal(100), unit="%"):
    denominator_value = _decimal(denominator)
    if denominator_value == 0:
        return _unavailable(display_name, unit, [numerator, denominator], numerator["data_date"], "分母为零")
    value = _decimal(numerator) / denominator_value * multiplier
    return _metric(
        display_name,
        value,
        _format_decimal(value),
        unit,
        numerator["data_date"],
        _latest_available_at([numerator, denominator]),
    )


def _subtract_metric(left, right, display_name, unit, extra=None):
    value = _decimal(left) - _decimal(right)
    precision = max(_precision(left), _precision(right))
    return _metric(
        display_name,
        value,
        _format_decimal(value, precision),
        unit,
        left["data_date"],
        _latest_available_at([left, right]),
        extra=extra,
    )


def compute_supply_metrics(today, yesterday, last_year):
    required = {"acceptance", "discount", "trading"}
    for group_name, group in [("today", today), ("yesterday", yesterday), ("last_year", last_year)]:
        if not required.issubset(group):
            raise ValueError(f"{group_name} 缺少字段：{sorted(required - set(group))}")

    names = {"acceptance": "承兑量", "discount": "贴现量", "trading": "交易量"}
    result = {}
    for key, display_name in names.items():
        result[f"{key}_amount"] = _reference_metric(today[key], display_name)
        result[f"{key}_mom"] = _change_metric(today[key], yesterday[key], f"{display_name}环比", key)
        result[f"{key}_yoy"] = _change_metric(today[key], last_year[key], f"{display_name}同比", key)
    result["acceptance_discount_ratio"] = _ratio_metric(today["discount"], today["acceptance"], "承贴比")
    return result


def compute_gap_metrics(maturity_total, discounted, workdays_left, recent5_daily_avg):
    result = {
        "maturity_total": _reference_metric(maturity_total, "本月贴现到期量"),
        "discounted": _reference_metric(discounted, "本月已贴现量"),
        "remaining_business_days": _reference_metric(workdays_left, "本月剩余工作日"),
        "recent5_daily_avg": _reference_metric(recent5_daily_avg, "近 5 个工作日日均贴现量"),
    }
    result["discount_gap"] = _subtract_metric(maturity_total, discounted, "缺口", maturity_total["unit"])
    workdays_value = _decimal(workdays_left)
    if workdays_value == 0:
        result["daily_required_amount"] = _unavailable(
            "日均需补量",
            maturity_total["unit"],
            [maturity_total, discounted, workdays_left],
            maturity_total["data_date"],
            "分母为零：本月剩余工作日为 0",
        )
    else:
        value = (_decimal(maturity_total) - _decimal(discounted)) / workdays_value
        result["daily_required_amount"] = _metric(
            "日均需补量",
            value,
            _format_decimal(value),
            maturity_total["unit"],
            maturity_total["data_date"],
            _latest_available_at([maturity_total, discounted, workdays_left]),
        )
    return result


def compute_rate_metrics(rates_by_tenor, cross_year_flag):
    if not isinstance(cross_year_flag, bool):
        raise ValueError("cross_year_flag 必须是布尔值")
    if not rates_by_tenor:
        raise ValueError("rates_by_tenor 不能为空")

    result = {}
    single_tenor = len(rates_by_tenor) == 1
    for tenor, series in rates_by_tenor.items():
        if not {"cross_year", "regular"}.issubset(series):
            raise ValueError(f"期限 {tenor} 必须同时提供 cross_year 与 regular")
        suffix = "" if single_tenor else "_" + "".join(character.lower() if character.isalnum() else "_" for character in tenor)
        cross = series["cross_year"]
        regular = series["regular"]
        cross_key = f"cross_year_bill_rate{suffix}"
        regular_key = f"regular_bill_rate{suffix}"
        spread_key = f"cross_year_regular_spread{suffix}"
        result[cross_key] = _reference_metric(cross, f"跨年票利率（{tenor}）")
        result[regular_key] = _reference_metric(regular, f"普通票利率（{tenor}）")
        result[cross_key]["cross_year_flag"] = cross_year_flag
        result[regular_key]["cross_year_flag"] = cross_year_flag
        if cross_year_flag:
            result[spread_key] = _subtract_metric(cross, regular, f"跨年票与普通票利差（{tenor}）", "百分点")
        else:
            result[spread_key] = _unavailable(
                f"跨年票与普通票利差（{tenor}）",
                "百分点",
                [cross, regular],
                cross["data_date"],
                "未提供跨年票标识",
            )
    return result


def compute_funding_metrics(omo, shibor_on, dr001, dr007, r007):
    if not {"injection", "maturity"}.issubset(omo):
        raise ValueError("omo 必须包含 injection 与 maturity")
    injection = omo["injection"]
    maturity = omo["maturity"]
    net = _decimal(injection) - _decimal(maturity)
    operation = "net_injection" if net > 0 else "net_withdrawal" if net < 0 else "balanced"
    display_name = "公开市场操作净回笼" if operation == "net_withdrawal" else "公开市场操作净投放"
    if operation == "balanced":
        display_name = "公开市场操作净投放"

    result = {
        "omo_injection": _reference_metric(injection, "逆回购投放"),
        "omo_maturity": _reference_metric(maturity, "逆回购到期"),
        "omo_net_injection": _subtract_metric(injection, maturity, display_name, injection["unit"], {"operation": operation}),
        "shibor_on": _reference_metric(shibor_on, "SHIBOR 隔夜"),
        "dr001": _reference_metric(dr001, "DR001"),
        "dr007": _reference_metric(dr007, "DR007"),
        "r007": _reference_metric(r007, "R007"),
        "dr001_shibor_spread": _subtract_metric(dr001, shibor_on, "DR001 与 SHIBOR 隔夜利差", "百分点"),
        "dr007_shibor_spread": _subtract_metric(dr007, shibor_on, "DR007 与 SHIBOR 隔夜利差", "百分点"),
        "r007_dr007_spread": _subtract_metric(r007, dr007, "R007 与 DR007 利差", "百分点"),
    }
    return result


def build_metrics_result(task_id, created_at, metrics, calculator_path, input_sha256):
    metrics_copy = copy.deepcopy(metrics)
    identity = json.dumps(
        {"task_id": task_id, "input_sha256": input_sha256, "metrics": metrics_copy},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "result_id": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        "calculator_path": str(calculator_path),
        "input_sha256": input_sha256,
        "created_at": created_at,
        "metrics": metrics_copy,
    }


def _input_hash(payload):
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def calculate_case(payload, calculator_path=None):
    for key in ["task_id", "created_at", "as_of_date"]:
        if key not in payload:
            raise ValueError(f"计算输入缺少 {key}")

    metrics = {}
    if "supply" in payload:
        supply = payload["supply"]
        metrics.update(compute_supply_metrics(supply["today"], supply["yesterday"], supply["last_year"]))
    if "gap" in payload:
        gap = payload["gap"]
        calendar_path = payload.get("calendar_path")
        workdays = workdays_left_field(payload["as_of_date"], calendar_path) if calendar_path else workdays_left_field(payload["as_of_date"])
        metrics.update(compute_gap_metrics(gap["maturity_total"], gap["discounted"], workdays, gap["recent5_daily_avg"]))
    if "rates" in payload:
        rates = payload["rates"]
        metrics.update(compute_rate_metrics(rates["rates_by_tenor"], rates["cross_year_flag"]))
    if "funding" in payload:
        funding = payload["funding"]
        metrics.update(compute_funding_metrics(funding["omo"], funding["shibor_on"], funding["dr001"], funding["dr007"], funding["r007"]))
    if not metrics:
        raise ValueError("计算输入至少包含 supply、gap、rates、funding 之一")

    return build_metrics_result(
        task_id=payload["task_id"],
        created_at=payload["created_at"],
        metrics=metrics,
        calculator_path=calculator_path or Path(__file__).resolve(),
        input_sha256=_input_hash(payload),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="票据市场日评确定性指标计算")
    parser.add_argument("--input", required=True, help="计算输入 JSON 路径")
    parser.add_argument("--output", required=True, help="指标结果 JSON 输出路径")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_path = Path(args.output)
    with input_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    result = calculate_case(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()
