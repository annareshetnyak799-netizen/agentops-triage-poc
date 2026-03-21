# TOOL_CONTRACTS — AgentOps Triage PoC

This document defines the tool interface contracts for the AgentOps Triage PoC.

The purpose of this document is to make tool integration implementation-ready by clarifying:
- what tools exist in the system,
- what each tool is allowed to do,
- what inputs it accepts,
- what outputs it returns,
- how failures are represented,
- what safety and timeout constraints apply.

This is a logical contract specification, not a final SDK or code-level interface.

---

## 1. Purpose

In this PoC, tools are the controlled mechanism by which the agent interacts with external knowledge and operational data.

Tools must be:
- explicit,
- bounded,
- auditable,
- safe by default,
- easy to mock in tests and evals.

The agent must not call arbitrary external systems directly.  
All external interactions should happen through defined tool contracts.

---

## 2. General principles

### 2.1 Read-only by default
All tools in the initial PoC are read-only unless explicitly marked otherwise.

The default assumption is:
- inspect,
- retrieve,
- search,
- summarize,
- compare,

but not:
- modify,
- rollback,
- restart,
- delete,
- scale,
- patch.

### 2.2 Structured input and output
Each tool must accept a structured input payload and return a structured output payload.

This ensures:
- predictable orchestration,
- easier validation,
- easier testing,
- easier observability.

### 2.3 Normalized failure handling
Tool failures must be returned in a consistent format.

The orchestrator should not need tool-specific error parsing for basic failure handling.

### 2.4 Bounded execution
Each tool must have:
- a timeout budget,
- clear failure behavior,
- defined retry expectations.

### 2.5 Auditability
Tool usage must be visible in:
- traces,
- logs,
- tool call records,
- evaluation artifacts.

### 2.6 Safety gating
A tool contract must define:
- what the tool is allowed to access,
- what sensitive data may appear,
- whether the tool is read-only,
- whether approval is ever needed.

---

## 3. Common tool interface

All tools conceptually implement the same interface.

### 3.1 Common input envelope

```json
{
  "tool_name": "metrics_tool",
  "session_id": "uuid",
  "arguments": {}
}
```

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `tool_name` | string | yes | Logical tool identifier |
| `session_id` | string | yes | Session UUID |
| `arguments` | object | yes | Tool-specific argument payload |

---

### 3.2 Common success output envelope

```json
{
  "status": "ok",
  "tool_name": "metrics_tool",
  "data": {},
  "meta": {
    "latency_ms": 420
  }
}
```

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `status` | string | yes | Must be `ok` for successful execution |
| `tool_name` | string | yes | Tool identifier |
| `data` | object | yes | Tool-specific normalized result |
| `meta` | object | no | Optional execution metadata |

---

### 3.3 Common error output envelope

```json
{
  "status": "error",
  "tool_name": "metrics_tool",
  "error": {
    "code": "TIMEOUT",
    "message": "Tool execution exceeded timeout budget",
    "details": {}
  },
  "meta": {
    "latency_ms": 5000
  }
}
```

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `status` | string | yes | Must be `error` for failed execution |
| `tool_name` | string | yes | Tool identifier |
| `error.code` | string | yes | Machine-readable failure code |
| `error.message` | string | yes | Human-readable message |
| `error.details` | object | no | Optional structured details |
| `meta` | object | no | Optional execution metadata |

---

## 4. Common tool error codes

| Code | Meaning |
|------|---------|
| `INVALID_ARGUMENTS` | Input arguments are malformed or incomplete |
| `UNAUTHORIZED` | Tool cannot access the target system |
| `FORBIDDEN` | Access is blocked by policy |
| `NOT_FOUND` | Requested entity or record does not exist |
| `TIMEOUT` | Execution exceeded timeout budget |
| `DEPENDENCY_UNAVAILABLE` | Downstream dependency is unavailable |
| `RATE_LIMITED` | Tool was rate-limited |
| `PARSE_ERROR` | Tool response could not be normalized |
| `INTERNAL_ERROR` | Unexpected tool-side failure |

---

## 5. Tool catalog

The initial PoC tool catalog includes:

- `metrics_tool`
- `logs_tool`
- `service_catalog_tool`
- `deployment_tool`
- `runbook_retrieval_tool`
- `incident_history_tool`

Not all tools must be fully implemented in the first milestone, but their contracts should be defined now.

---

## 6. metrics_tool

### 6.1 Purpose
Retrieve service-level metrics relevant to an incident.

Typical use cases:
- error rate inspection,
- latency inspection,
- time-window comparison,
- recent anomaly checks.

### 6.2 Access mode
- Read-only
- No approval required

### 6.3 Input contract

```json
{
  "service": "payments-api",
  "environment": "prod",
  "metrics": ["error_rate", "latency_p95"],
  "time_range": {
    "start": "2026-03-20T11:00:00Z",
    "end": "2026-03-20T11:30:00Z"
  }
}
```

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `service` | string | yes | Target service name |
| `environment` | string | no | Environment such as `prod` |
| `metrics` | array[string] | yes | Requested metric names |
| `time_range.start` | datetime | yes | Interval start |
| `time_range.end` | datetime | yes | Interval end |

### 6.4 Success output contract

```json
{
  "status": "ok",
  "tool_name": "metrics_tool",
  "data": {
    "service": "payments-api",
    "environment": "prod",
    "results": [
      {
        "metric": "error_rate",
        "value": 12.4,
        "unit": "percent",
        "window": "2026-03-20T11:00:00Z/2026-03-20T11:30:00Z",
        "summary": "Error rate rose from 0.8% to 12.4%"
      },
      {
        "metric": "latency_p95",
        "value": 840,
        "unit": "ms",
        "window": "2026-03-20T11:00:00Z/2026-03-20T11:30:00Z",
        "summary": "p95 latency increased 3x"
      }
    ]
  },
  "meta": {
    "latency_ms": 420
  }
}
```

### 6.5 Failure notes
Typical failures:
- metric backend unavailable,
- unknown service,
- invalid time range,
- timeout.

### 6.6 Timeout and retry policy
- Timeout: 5 seconds
- Retry: up to 1 retry for transient backend failures
- No retry for invalid arguments

---

## 7. logs_tool

### 7.1 Purpose
Retrieve recent logs related to a service and incident window.

Typical use cases:
- searching error spikes,
- finding stack traces,
- comparing pre/post deploy behavior.

### 7.2 Access mode
- Read-only
- No approval required

### 7.3 Input contract

```json
{
  "service": "payments-api",
  "environment": "prod",
  "query": "error OR exception OR timeout",
  "time_range": {
    "start": "2026-03-20T11:00:00Z",
    "end": "2026-03-20T11:30:00Z"
  },
  "limit": 20
}
```

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `service` | string | yes | Target service |
| `environment` | string | no | Environment name |
| `query` | string | yes | Log query string |
| `time_range.start` | datetime | yes | Interval start |
| `time_range.end` | datetime | yes | Interval end |
| `limit` | integer | no | Max number of log entries |

### 7.4 Success output contract

```json
{
  "status": "ok",
  "tool_name": "logs_tool",
  "data": {
    "service": "payments-api",
    "entries": [
      {
        "timestamp": "2026-03-20T11:07:02Z",
        "level": "ERROR",
        "message": "PaymentProviderTimeout: upstream request exceeded deadline"
      },
      {
        "timestamp": "2026-03-20T11:08:11Z",
        "level": "ERROR",
        "message": "NullPointerException in charge creation flow"
      }
    ],
    "summary": "Multiple new errors appeared after deployment"
  },
  "meta": {
    "latency_ms": 760
  }
}
```

### 7.5 Failure notes
Typical failures:
- log backend unavailable,
- query parse failure,
- service not found,
- result truncation.

### 7.6 Timeout and retry policy
- Timeout: 8 seconds
- Retry: up to 1 retry for dependency unavailability
- No retry for invalid query syntax

---

## 8. service_catalog_tool

### 8.1 Purpose
Return metadata about a service.

Typical use cases:
- determining owner/team,
- checking dependencies,
- identifying tier/criticality,
- finding linked runbooks.

### 8.2 Access mode
- Read-only
- No approval required

### 8.3 Input contract

```json
{
  "service": "payments-api"
}
```

### 8.4 Success output contract

```json
{
  "status": "ok",
  "tool_name": "service_catalog_tool",
  "data": {
    "service": "payments-api",
    "owner_team": "payments-platform",
    "tier": "tier-1",
    "dependencies": ["postgres-payments", "payment-provider-gateway"],
    "runbook_refs": ["runbook:payments-api-primary"]
  },
  "meta": {
    "latency_ms": 120
  }
}
```

### 8.5 Timeout and retry policy
- Timeout: 3 seconds
- Retry: up to 1 retry for transient dependency failure

---

## 9. deployment_tool

### 9.1 Purpose
Retrieve recent deployment/change metadata for a service.

Typical use cases:
- checking whether an incident correlates with a rollout,
- identifying version changes,
- comparing before/after deployment windows.

### 9.2 Access mode
- Read-only in PoC
- No approval required for retrieval
- Any future write-like action based on this tool remains out of scope

### 9.3 Input contract

```json
{
  "service": "payments-api",
  "environment": "prod",
  "time_range": {
    "start": "2026-03-20T10:00:00Z",
    "end": "2026-03-20T11:30:00Z"
  }
}
```

### 9.4 Success output contract

```json
{
  "status": "ok",
  "tool_name": "deployment_tool",
  "data": {
    "service": "payments-api",
    "deployments": [
      {
        "deployment_id": "dep-2026-03-20-17",
        "version": "2026.03.20-17",
        "started_at": "2026-03-20T11:02:00Z",
        "completed_at": "2026-03-20T11:05:00Z",
        "status": "completed"
      }
    ],
    "summary": "A deployment completed shortly before the incident window"
  },
  "meta": {
    "latency_ms": 240
  }
}
```

### 9.5 Timeout and retry policy
- Timeout: 4 seconds
- Retry: up to 1 retry for transient failure

---

## 10. runbook_retrieval_tool

### 10.1 Purpose
Retrieve relevant runbooks or troubleshooting documents.

Typical use cases:
- grounding investigation steps,
- surfacing known diagnostic procedures,
- linking service-specific operational guidance.

### 10.2 Access mode
- Read-only
- No approval required

### 10.3 Input contract

```json
{
  "service": "payments-api",
  "query": "high 5xx after deploy",
  "limit": 3
}
```

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `service` | string | no | Service filter if known |
| `query` | string | yes | Retrieval query |
| `limit` | integer | no | Max number of returned docs |

### 10.4 Success output contract

```json
{
  "status": "ok",
  "tool_name": "runbook_retrieval_tool",
  "data": {
    "documents": [
      {
        "doc_id": "runbook:payments-api-primary",
        "title": "Payments API Primary Runbook",
        "snippet": "If 5xx rises immediately after deploy, compare error classes and verify dependency health first."
      }
    ],
    "summary": "Found 1 relevant runbook"
  },
  "meta": {
    "latency_ms": 180
  }
}
```

### 10.5 Timeout and retry policy
- Timeout: 3 seconds
- Retry: optional 1 retry for transient retrieval backend issues

---

## 11. incident_history_tool

### 11.1 Purpose
Search prior incidents similar to the current one.

Typical use cases:
- surfacing repeated patterns,
- identifying known mitigations,
- improving hypothesis generation.

### 11.2 Access mode
- Read-only
- No approval required

### 11.3 Input contract

```json
{
  "service": "payments-api",
  "query": "5xx spike after deploy",
  "limit": 5
}
```

### 11.4 Success output contract

```json
{
  "status": "ok",
  "tool_name": "incident_history_tool",
  "data": {
    "matches": [
      {
        "incident_id": "inc-1842",
        "title": "Payments API 5xx surge after release",
        "resolved_with": "Rollback and config correction",
        "similarity": 0.82
      }
    ],
    "summary": "Found 1 similar past incident"
  },
  "meta": {
    "latency_ms": 210
  }
}
```

### 11.5 Timeout and retry policy
- Timeout: 3 seconds
- Retry: optional 1 retry for transient backend issues

---

## 12. Tool observability requirements

Every tool execution should emit or persist at least the following metadata:
- `session_id`
- `tool_name`
- `input_hash` or sanitized input summary
- `status`
- `started_at`
- `completed_at`
- `latency_ms`
- `error_code` if failed

Optional fields:
- dependency name
- result count
- truncation flag
- retry count

---

## 13. Tool safety requirements

### 13.1 Input sanitation
Tool inputs derived from user text or retrieved text must be sanitized before execution where appropriate.

### 13.2 Sensitive output handling
If a tool can return sensitive content, the system should:
- redact before logging,
- minimize exposure in traces,
- pass only necessary structured content forward.

### 13.3 No arbitrary execution
Tools must not:
- execute shell commands,
- issue write operations,
- make unrestricted outbound calls,
- bypass policy enforcement.

### 13.4 Approval boundary
If a future tool may trigger real-world change, it must:
- be marked as write-capable,
- require explicit approval,
- be separated from the read-only tool set.

---

## 14. Mocking and eval guidance

Each tool contract should be easy to mock for:
- local development,
- offline testing,
- deterministic evaluation,
- demo scenarios.

Recommended mock strategy:
- fixed JSON fixtures,
- deterministic responses by incident type,
- explicit error simulation for timeout/unavailable cases.

---

## 15. Recommended implementation mapping

The tool layer in code should ideally include:
- one interface/base abstraction for tools,
- one schema/model per tool input,
- one schema/model per tool output,
- a shared normalized error model,
- a registry for available tools.

Possible code structure:

```text
src/tools/
  base.py
  registry.py
  metrics_tool.py
  logs_tool.py
  service_catalog_tool.py
  deployment_tool.py
  runbook_retrieval_tool.py
  incident_history_tool.py
  schemas.py
```

---

## 16. Open questions

1. Which tools will be real integrations in the first implementation, and which will stay mocked?
2. Should retrieval tools and operational tools share one registry or separate registries?
3. Should normalized tool outputs always become `Observation` objects immediately?
4. How much raw tool output should be persisted?
5. Should tool-level rate limiting be handled inside each tool or in a shared wrapper?

---

## 17. Definition of done

The tool contract layer is considered implementation-ready when:
- each planned tool has a defined purpose,
- each tool has explicit input and output schemas,
- failure behavior is documented,
- timeout and retry rules are clear,
- observability and safety requirements are explicit,
- developers can implement or mock tools without major ambiguity.
