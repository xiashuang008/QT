import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        record = {
            "event": payload.get("event", "PostToolUse"),
            "tool_name": payload.get("tool_name", payload.get("tool", "unknown")),
            "session_id": payload.get("session_id"),
            "tool_call_id": payload.get("tool_call_id", payload.get("call_id")),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        log_path = root / "output" / "hook-audit.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception as error:
        try:
            log_path = root / "output" / "hook-audit-error.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(f"{datetime.now(timezone.utc).isoformat()} {type(error).__name__}\n")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
