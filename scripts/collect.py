import argparse
import csv
import hashlib
import json
import os
import tempfile
from datetime import date
from pathlib import Path


def fetch_shex(start_date, end_date):
    # TODO: 接入票交所真实只读接口，返回与夹具字段相同的记录列表。
    raise NotImplementedError("票交所真实数据源接口尚未接入")


def fetch_pboct(start_date, end_date):
    # TODO: 接入人民银行真实只读接口，返回与夹具字段相同的记录列表。
    raise NotImplementedError("人民银行真实数据源接口尚未接入")


def fetch_cfets(start_date, end_date):
    # TODO: 接入 CFETS/货币网真实只读接口，返回与夹具字段相同的记录列表。
    raise NotImplementedError("CFETS/货币网真实数据源接口尚未接入")


def _atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _boolean(value):
    return str(value).strip().lower() in {"1", "true", "yes"}


def _number(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def collect_fixture(fixture_path, output_root, snapshot_date, created_at):
    fixture = Path(fixture_path).resolve()
    if not fixture.is_file():
        raise FileNotFoundError(f"固定数据夹具缺失：{fixture}")
    with fixture.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("固定数据夹具不能为空")

    destination = Path(output_root).resolve() / str(snapshot_date)
    destination.mkdir(parents=True, exist_ok=True)
    snapshot_file = destination / "source_data.csv"
    _atomic_write(snapshot_file, fixture.read_text(encoding="utf-8-sig"))

    fields = []
    for row in rows:
        status = row.get("status") or ("missing" if not row.get("value") else "present")
        value = row.get("value", "")
        fields.append({
            "field": row["field"],
            "value": _number(value) if status == "present" else None,
            "raw_value": value,
            "unit": row.get("unit", ""),
            "data_date": row["data_date"],
            "source_institution": row["source_institution"],
            "definition": row["definition"],
            "available_at": row["available_at"],
            "disclosure_time_confirmed": _boolean(row.get("disclosure_time_confirmed", False)),
            "status": status,
            "required": _boolean(row.get("required", True)),
            "missing_reason": row.get("missing_reason", ""),
        })
    dates = [item["data_date"] for item in fields]
    line_count = len(fixture.read_text(encoding="utf-8-sig").splitlines())
    manifest = {
        "schema_version": "1.0.0",
        "task_id": f"snapshot-{snapshot_date}",
        "snapshot_id": f"snapshot-{snapshot_date}",
        "expected_trading_date": str(snapshot_date),
        "created_at": created_at,
        "source_files": [{
            "path": str(snapshot_file),
            "sha256": hashlib.sha256(snapshot_file.read_bytes()).hexdigest(),
            "format": "CSV",
            "row_count": len(rows),
            "line_count": line_count,
            "date_range": {"start": min(dates), "end": max(dates)},
            "source_institutions": sorted({item["source_institution"] for item in fields}),
        }],
        "fields": fields,
        "missing_fields": [item["field"] for item in fields if item["status"] == "missing"],
    }
    manifest_path = destination / "manifest.json"
    _atomic_write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="用固定夹具生成日评数据快照")
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--output-root", default="data/snapshots")
    args = parser.parse_args(argv)
    manifest = collect_fixture(args.fixture, args.output_root, args.date, args.created_at)
    print(json.dumps({"snapshot_id": manifest["snapshot_id"], "fields": len(manifest["fields"]), "missing": manifest["missing_fields"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
