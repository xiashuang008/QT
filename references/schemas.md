# 字段与报告产物 JSON 结构

本文定义工作流交换结构的最低字段要求。各结构使用 JSON Schema 2020-12 表示；`path` 字段在运行时必须是绝对路径，`sha256` 必须是小写 SHA-256 十六进制字符串。所有验收阈值仍引用 `policies/policy.json`，本文不定义通过阈值。

## 1. 快照 manifest

快照 manifest 登记文件身份、字段口径与可得时点，字段值缺失时必须显式登记，不得用 `bfill` 补齐。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "snapshot-manifest.schema.json",
  "type": "object",
  "required": ["schema_version", "task_id", "snapshot_id", "expected_trading_date", "created_at", "source_files", "fields"],
  "properties": {
    "schema_version": {"type": "string"},
    "task_id": {"type": "string"},
    "snapshot_id": {"type": "string"},
    "expected_trading_date": {"type": "string", "format": "date"},
    "created_at": {"type": "string", "format": "date-time"},
    "source_files": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path", "sha256", "format"],
        "properties": {
          "path": {"type": "string", "description": "绝对路径"},
          "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
          "format": {"type": "string", "enum": ["CSV", "JSON"]}
        }
      }
    },
    "fields": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["field", "data_date", "source_institution", "definition", "available_at", "disclosure_time_confirmed", "status"],
        "properties": {
          "field": {"type": "string"},
          "value": {},
          "unit": {"type": "string"},
          "data_date": {"type": "string", "format": "date"},
          "source_institution": {"type": "string"},
          "definition": {"type": "string"},
          "available_at": {"type": "string", "description": "运行时解析为带时区时点；保守假设或待确认状态须与 pit_rules.json 一致"},
          "disclosure_time_confirmed": {"type": "boolean"},
          "status": {"type": "string", "enum": ["present", "missing"]},
          "missing_reason": {"type": "string"},
          "manual_entry_at": {"type": "string", "format": "date-time"}
        }
      }
    }
  }
}
```

## 2. 指标结果

指标结果只能由 `scripts/calculator.py` 生成。`raw_value` 保存原始数值文本，`value` 保存结构化值；曲线类指标可使用数组或对象作为 `value`。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "metrics-result.schema.json",
  "type": "object",
  "required": ["schema_version", "task_id", "result_id", "calculator_path", "input_sha256", "created_at", "metrics"],
  "properties": {
    "schema_version": {"type": "string"},
    "task_id": {"type": "string"},
    "result_id": {"type": "string"},
    "calculator_path": {"type": "string", "description": "scripts/calculator.py 的绝对路径"},
    "input_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "created_at": {"type": "string", "format": "date-time"},
    "metrics": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["display_name", "value", "raw_value", "unit", "data_date", "available_at"],
        "properties": {
          "display_name": {"type": "string"},
          "value": {},
          "raw_value": {"type": "string"},
          "unit": {"type": "string"},
          "data_date": {"type": "string", "format": "date"},
          "available_at": {"type": "string", "format": "date-time"},
          "base_period": {"type": "string"},
          "source_fields": {"type": "array", "items": {"type": "string"}}
        }
      }
    }
  }
}
```

## 3. 候选日评登记结构

候选正文为 Markdown，本 JSON 登记正文身份、信息截止时点、四模块数据日期及指标来源，不替代正文文件。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "candidate-review.schema.json",
  "type": "object",
  "required": ["schema_version", "task_id", "candidate_id", "version", "content_path", "content_sha256", "information_cutoff", "metrics_result", "modules", "created_at"],
  "properties": {
    "schema_version": {"type": "string"},
    "task_id": {"type": "string"},
    "candidate_id": {"type": "string"},
    "version": {"type": "string"},
    "content_path": {"type": "string", "description": "Markdown 正文绝对路径"},
    "content_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "information_cutoff": {"type": "string", "format": "date-time"},
    "metrics_result": {
      "type": "object",
      "required": ["path", "sha256"],
      "properties": {
        "path": {"type": "string"},
        "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
      }
    },
    "modules": {
      "type": "object",
      "required": ["supply", "gap", "bill_rate", "funding"],
      "properties": {
        "supply": {"$ref": "#/$defs/module"},
        "gap": {"$ref": "#/$defs/module"},
        "bill_rate": {"$ref": "#/$defs/module"},
        "funding": {"$ref": "#/$defs/module"}
      }
    },
    "created_at": {"type": "string", "format": "date-time"}
  },
  "$defs": {
    "module": {
      "type": "object",
      "required": ["title", "data_date", "section"],
      "properties": {
        "title": {"type": "string"},
        "data_date": {"type": "string", "format": "date"},
        "section": {"type": "string", "description": "正文中的模块定位"}
      }
    }
  }
}
```

## 4. 核验结论

每轮核验均登记新上下文身份、必要检查覆盖和结果；`passed` 仅代表本轮审查结论，不代表人工批准。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "verification-result.schema.json",
  "type": "object",
  "required": ["schema_version", "task_id", "candidate_id", "candidate_sha256", "round", "context_id", "checks", "unresolved_issue_ids", "conclusion", "created_at"],
  "properties": {
    "schema_version": {"type": "string"},
    "task_id": {"type": "string"},
    "candidate_id": {"type": "string"},
    "candidate_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "round": {"type": "integer", "minimum": 1},
    "context_id": {"type": "string"},
    "checks": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "status", "evidence_paths"],
        "properties": {
          "name": {"type": "string"},
          "status": {"type": "string", "enum": ["passed", "failed", "blocked"]},
          "evidence_paths": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "unresolved_issue_ids": {"type": "array", "items": {"type": "string"}},
    "issue_ledger_path": {"type": "string"},
    "conclusion": {"type": "string", "enum": ["passed", "failed", "blocked"]},
    "created_at": {"type": "string", "format": "date-time"}
  }
}
```

## 5. 问题项台账报告

该结构是随审查产物保存的不可变台账报告；数字不一致项应在 `details` 中登记正文值、期望值与差额。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "issue-ledger-report.schema.json",
  "type": "object",
  "required": ["schema_version", "task_id", "candidate_id", "issues"],
  "properties": {
    "schema_version": {"type": "string"},
    "task_id": {"type": "string"},
    "candidate_id": {"type": "string"},
    "issues": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "severity", "check_type", "affected_artifacts", "description", "evidence_required", "status"],
        "properties": {
          "id": {"type": "string"},
          "severity": {"type": "string"},
          "check_type": {"type": "string"},
          "affected_artifacts": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["path", "location"],
              "properties": {
                "path": {"type": "string"},
                "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                "location": {"type": "string"}
              }
            }
          },
          "description": {"type": "string"},
          "details": {
            "type": "object",
            "properties": {
              "actual": {},
              "expected": {},
              "difference": {}
            }
          },
          "evidence_required": {"type": "array", "items": {"type": "string"}},
          "status": {"type": "string", "enum": ["open", "resolved"]}
        }
      }
    }
  }
}
```

## 6. `state.json`

状态文件由控制器写入，恢复时必须先校验产物和哈希；`revision_round` 是状态计数，不是上限定义。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "state.schema.json",
  "type": "object",
  "required": ["schema_version", "task_id", "request_id", "status", "pending_role", "revision_round", "artifacts", "unresolved_issue_ids", "version", "updated_at"],
  "properties": {
    "schema_version": {"type": "string"},
    "task_id": {"type": "string"},
    "request_id": {"type": "string"},
    "status": {"type": "string", "enum": ["created", "data_ready", "calculated", "drafted", "verified", "approved", "published"]},
    "pending_role": {"type": ["string", "null"]},
    "revision_round": {"type": "integer", "minimum": 0},
    "artifacts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["kind", "path", "sha256"],
        "properties": {
          "kind": {"type": "string"},
          "path": {"type": "string"},
          "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
        }
      }
    },
    "unresolved_issue_ids": {"type": "array", "items": {"type": "string"}},
    "version": {"type": "string"},
    "consecutive_verification_passes": {"type": "integer", "minimum": 0},
    "tool_call_count": {"type": "integer", "minimum": 0},
    "total_duration_seconds": {"type": "number", "minimum": 0},
    "updated_at": {"type": "string", "format": "date-time"}
  }
}
```

## 7. `issues.json`

`issues.json` 是控制器维护的当前问题项状态，与每轮不可变核验台账报告分开保存。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "issues.schema.json",
  "type": "object",
  "required": ["schema_version", "task_id", "issues", "updated_at"],
  "properties": {
    "schema_version": {"type": "string"},
    "task_id": {"type": "string"},
    "issues": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "severity", "affected_artifacts", "evidence_required", "status", "opened_round"],
        "properties": {
          "id": {"type": "string"},
          "severity": {"type": "string"},
          "affected_artifacts": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["path", "location"],
              "properties": {
                "path": {"type": "string"},
                "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                "location": {"type": "string"}
              }
            }
          },
          "evidence_required": {"type": "array", "items": {"type": "string"}},
          "status": {"type": "string", "enum": ["open", "resolved"]},
          "opened_round": {"type": "integer", "minimum": 1},
          "resolved_round": {"type": ["integer", "null"], "minimum": 1},
          "resolution_evidence": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "updated_at": {"type": "string", "format": "date-time"}
  }
}
```

## 8. 版本注册表

版本注册表采用 JSONL，每行符合以下记录结构。批准记录仅通过独立路径引用，不嵌入版本记录。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "version-registry-record.schema.json",
  "type": "object",
  "required": ["schema_version", "version", "task_id", "artifacts", "baseline_comparison", "regression_result", "approval_record_path", "rollback_target", "registered_at"],
  "properties": {
    "schema_version": {"type": "string"},
    "version": {"type": "string"},
    "task_id": {"type": "string"},
    "parent_version": {"type": ["string", "null"]},
    "artifacts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["kind", "path", "sha256"],
        "properties": {
          "kind": {"type": "string"},
          "path": {"type": "string"},
          "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
        }
      }
    },
    "baseline_comparison": {"type": "object"},
    "regression_result": {"type": "object"},
    "approval_record_path": {"type": "string", "description": "独立批准记录绝对路径"},
    "rollback_target": {"type": ["string", "null"]},
    "registered_at": {"type": "string", "format": "date-time"}
  }
}
```

## 9. 批准记录

批准记录独立保存，必须具名、绑定具体版本和候选哈希、含有效期与结论。过期、版本不符或哈希不符均不能支持发布。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "approval-record.schema.json",
  "type": "object",
  "required": ["schema_version", "approval_id", "task_id", "version", "candidate_sha256", "approver_name", "approver_role", "conclusion", "approved_at", "expires_at"],
  "properties": {
    "schema_version": {"type": "string"},
    "approval_id": {"type": "string"},
    "task_id": {"type": "string"},
    "version": {"type": "string"},
    "candidate_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "approver_name": {"type": "string"},
    "approver_role": {"type": "string"},
    "conclusion": {"type": "string", "enum": ["approve", "reject"]},
    "approved_at": {"type": "string", "format": "date-time"},
    "expires_at": {"type": "string", "format": "date-time"}
  }
}
```
