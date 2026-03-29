# API_SPEC — AgentOps Triage PoC

This document defines the external API contract for the AgentOps Triage PoC.

The goal of this API is to let a client:
- submit an incident,
- receive a structured triage response,
- inspect session state and trace,
- approve or reject gated actions,
- monitor service health and metrics.

The API is designed for a safe-by-default PoC:
- read/investigation flows are allowed,
- risky or write-like actions are gated behind approval,
- all outputs are structured and traceable.

---

## 1. General principles

### 1.1 API style
- Transport: HTTP/JSON
- Versioning: PoC starts unversioned, but endpoints should be designed to support `/v1/...` later
- Content type: `application/json`
- Time format: ISO 8601 in UTC
- IDs: UUID strings unless noted otherwise

### 1.2 Session-oriented execution
All triage operations are tied to `session_id`.

A session represents one bounded incident investigation lifecycle:
- incident intake,
- planning,
- retrieval/tool use,
- evidence collection,
- analysis,
- optional approval,
- final or partial report.

### 1.3 Safe-by-default behavior
The API must not trigger unsafe or write-like actions automatically.

If the system determines that a proposed action is risky or policy-gated, it must:
- stop before executing it,
- return an approval request,
- wait for explicit human input.

### 1.4 Structured outputs
All agent outputs returned by the API must be structured and machine-readable.

At minimum, responses should contain:
- hypotheses,
- prioritized next steps,
- references/evidence,
- safety notes,
- session metadata.

### 1.5 Partial completion is valid
If some tools fail or evidence is incomplete, the API may return a partial triage result.

In that case, the response must explicitly include:
- uncertainty,
- failed dependencies,
- recommended follow-up investigation.

---

## 2. Authentication and authorization

### 2.1 PoC mode
For the PoC, authentication may be simplified.

Supported options:
- no auth in local/dev mode,
- static API key header in shared demo environments.

### 2.2 Recommended header

```http
X-API-Key: <token>
```

### 2.3 Future direction
Production evolution may add:
- JWT/OAuth2
- RBAC
- audit-scoped approvals
- tenant isolation

These are out of scope for the initial PoC.

---

## 3. Base response conventions

### 3.1 Success response shape
All successful responses should follow this general shape:

```json
{
  "status": "ok",
  "data": {},
  "meta": {}
}
```

### 3.2 Error response shape
All errors should follow this shape:

```json
{
  "status": "error",
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Human-readable error message",
    "details": {}
  },
  "meta": {
    "request_id": "uuid"
  }
}
```

### 3.3 Common error codes

| Code | Meaning |
|------|---------|
| `INVALID_REQUEST` | Request payload is malformed or missing required fields |
| `UNAUTHORIZED` | Missing or invalid auth credentials |
| `FORBIDDEN` | Caller is not allowed to perform this action |
| `NOT_FOUND` | Requested session/resource does not exist |
| `CONFLICT` | Resource is in a conflicting state |
| `VALIDATION_FAILED` | Semantic validation failed |
| `POLICY_BLOCKED` | Operation blocked by safety/policy layer |
| `TOOL_FAILURE` | External/internal tool execution failed |
| `TIMEOUT` | Request or internal execution timed out |
| `INTERNAL_ERROR` | Unexpected server-side failure |

### 3.4 Common metadata
Where relevant, responses may include:

```json
{
  "meta": {
    "request_id": "uuid",
    "session_id": "uuid",
    "generated_at": "2026-03-20T12:00:00Z"
  }
}
```

---

## 4. Domain objects

This section defines the core response/request objects used across endpoints.

### 4.1 IncidentInput

```json
{
  "title": "High 5xx rate",
  "service": "payments-api",
  "severity": "P1",
  "timestamp": "2026-03-20T11:22:00Z",
  "summary": "Error rate increased after deploy",
  "signals": [
    "5xx > 12%",
    "latency p95 up 3x"
  ],
  "environment": "prod",
  "reporter": "oncall-engineer"
}
```

#### Field definitions

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `title` | string | yes | Short incident title |
| `service` | string | yes | Primary affected service |
| `severity` | string | yes | Incident severity, e.g. P1/P2/P3 |
| `timestamp` | string (ISO 8601) | yes | Incident report timestamp |
| `summary` | string | yes | Human-readable summary |
| `signals` | array[string] | no | Initial observed signals |
| `environment` | string | no | Environment, e.g. prod/staging |
| `reporter` | string | no | Human/source that reported the incident |

---

### 4.2 Hypothesis

```json
{
  "id": "uuid",
  "statement": "Recent deployment introduced elevated 5xx responses in payments-api",
  "confidence": 0.78,
  "status": "active",
  "supporting_refs": [
    "obs:metrics-1",
    "kb:runbook-42"
  ]
}
```

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | yes | Hypothesis identifier |
| `statement` | string | yes | Candidate explanation |
| `confidence` | number | yes | Confidence score in range 0..1 |
| `status` | string | yes | e.g. `active`, `weakened`, `discarded` |
| `supporting_refs` | array[string] | no | References to observations/docs |

---

### 4.3 NextStep

```json
{
  "priority": 1,
  "action": "Inspect recent deployment logs for payment error spikes",
  "rationale": "Correlates with timing of 5xx increase",
  "requires_approval": false
}
```

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `priority` | integer | yes | Lower means higher priority |
| `action` | string | yes | Recommended investigation/remediation step |
| `rationale` | string | no | Why this step matters |
| `requires_approval` | boolean | yes | Whether explicit approval is required |

---

### 4.4 Reference

```json
{
  "id": "obs:metrics-1",
  "type": "observation",
  "source": "metrics_tool",
  "title": "payments-api 5xx error rate",
  "snippet": "5xx increased from 0.8% to 12.4% after 11:05 UTC"
}
```

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | yes | Reference identifier |
| `type` | string | yes | `observation`, `kb_doc`, `tool_result`, etc. |
| `source` | string | yes | Origin system or tool |
| `title` | string | no | Short label |
| `snippet` | string | no | Relevant evidence excerpt |

---

### 4.5 SafetyNote

```json
{
  "type": "policy",
  "message": "Rollback suggestion is gated and requires explicit approval",
  "severity": "medium"
}
```

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `type` | string | yes | e.g. `policy`, `redaction`, `uncertainty` |
| `message` | string | yes | Human-readable note |
| `severity` | string | yes | `low`, `medium`, `high` |

---

### 4.6 ApprovalRequest

```json
{
  "approval_id": "uuid",
  "action_type": "rollback_deployment",
  "reason": "Potentially production-impacting write action",
  "risk_level": "high",
  "status": "pending"
}
```

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `approval_id` | string | yes | Approval identifier |
| `action_type` | string | yes | Type of gated action |
| `reason` | string | yes | Why approval is needed |
| `risk_level` | string | yes | `low`, `medium`, `high` |
| `status` | string | yes | `pending`, `approved`, `rejected` |

---

### 4.7 TriageReport

```json
{
  "incident_summary": {
    "title": "High 5xx rate",
    "service": "payments-api",
    "severity": "P1"
  },
  "status": "partial_completed",
  "hypotheses": [],
  "next_steps": [],
  "refs": [],
  "safety_notes": [],
  "approval_requests": [],
  "unknowns": [
    "Deployment metadata tool unavailable"
  ]
}
```

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `incident_summary` | object | yes | Normalized summary of the incident |
| `status` | string | yes | `completed`, `partial_completed`, `waiting_approval`, `failed` |
| `hypotheses` | array[Hypothesis] | yes | Current candidate explanations |
| `next_steps` | array[NextStep] | yes | Ordered recommended next steps |
| `refs` | array[Reference] | yes | Evidence references |
| `safety_notes` | array[SafetyNote] | yes | Safety/policy/uncertainty notes |
| `approval_requests` | array[ApprovalRequest] | no | Present if approval is needed |
| `unknowns` | array[string] | no | Known gaps or unresolved questions |

---

## 5. Endpoint overview

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/incident` | Create triage session and get initial/final triage response |
| `GET` | `/sessions/{session_id}` | Get current session state and latest triage report |
| `GET` | `/sessions/{session_id}/trace` | Inspect session execution trace |
| `POST` | `/sessions/{session_id}/approval` | Approve or reject a gated action |
| `GET` | `/health` | Service health check |
| `GET` | `/metrics` | Prometheus-style metrics endpoint |

---

## 6. POST /incident

Create a new triage session and start the investigation flow.

Depending on implementation mode, this endpoint may:
- return the first triage result synchronously,
- or return an accepted session and let the client poll for updates.

For the PoC, synchronous response is preferred if TTFA remains acceptable.

### Request

```json
{
  "title": "High 5xx rate",
  "service": "payments-api",
  "severity": "P1",
  "timestamp": "2026-03-20T11:22:00Z",
  "summary": "Error rate increased after deploy",
  "signals": [
    "5xx > 12%",
    "latency p95 up 3x"
  ],
  "environment": "prod",
  "reporter": "oncall-engineer"
}
```

### Response — success

```json
{
  "status": "ok",
  "data": {
    "session_id": "8f8d7d22-1f3e-4e8c-8ca0-4dc4b1d83f29",
    "report": {
      "incident_summary": {
        "title": "High 5xx rate",
        "service": "payments-api",
        "severity": "P1"
      },
      "status": "completed",
      "hypotheses": [
        {
          "id": "b16fcf1c-4d60-4fa8-b0f4-3249d15558ed",
          "statement": "Recent deployment likely introduced elevated 5xx responses in payments-api",
          "confidence": 0.81,
          "status": "active",
          "supporting_refs": [
            "obs:metrics-1",
            "obs:deploy-1"
          ]
        }
      ],
      "next_steps": [
        {
          "priority": 1,
          "action": "Inspect error logs for stack traces after the latest deployment",
          "rationale": "Needed to confirm whether the issue is code-path specific",
          "requires_approval": false
        }
      ],
      "refs": [
        {
          "id": "obs:metrics-1",
          "type": "observation",
          "source": "metrics_tool",
          "title": "payments-api 5xx error rate",
          "snippet": "5xx increased from 0.8% to 12.4% after 11:05 UTC"
        }
      ],
      "safety_notes": [
        {
          "type": "uncertainty",
          "message": "Root cause is not confirmed yet; hypothesis is evidence-backed but preliminary",
          "severity": "low"
        }
      ],
      "approval_requests": [],
      "unknowns": []
    }
  },
  "meta": {
    "request_id": "9a2a4976-93f0-434e-ac39-b95b4f13f4ba",
    "session_id": "8f8d7d22-1f3e-4e8c-8ca0-4dc4b1d83f29",
    "generated_at": "2026-03-20T11:22:14Z"
  }
}
```

### Response — approval required

```json
{
  "status": "ok",
  "data": {
    "session_id": "8f8d7d22-1f3e-4e8c-8ca0-4dc4b1d83f29",
    "report": {
      "incident_summary": {
        "title": "High 5xx rate",
        "service": "payments-api",
        "severity": "P1"
      },
      "status": "waiting_approval",
      "hypotheses": [
        {
          "id": "uuid",
          "statement": "Rolling back the latest deployment may mitigate the issue",
          "confidence": 0.73,
          "status": "active",
          "supporting_refs": [
            "obs:deploy-1",
            "obs:metrics-1"
          ]
        }
      ],
      "next_steps": [
        {
          "priority": 1,
          "action": "Rollback latest payments-api deployment",
          "rationale": "Correlated deploy timing and error spike",
          "requires_approval": true
        }
      ],
      "refs": [],
      "safety_notes": [
        {
          "type": "policy",
          "message": "Rollback is considered a gated action and was not executed automatically",
          "severity": "medium"
        }
      ],
      "approval_requests": [
        {
          "approval_id": "79ef42c6-d4b8-4f76-a3d5-d4d74d1827b9",
          "action_type": "rollback_deployment",
          "reason": "Production-impacting change requires human approval",
          "risk_level": "high",
          "status": "pending"
        }
      ],
      "unknowns": []
    }
  },
  "meta": {
    "request_id": "uuid",
    "session_id": "uuid",
    "generated_at": "2026-03-20T11:22:14Z"
  }
}
```

### Response codes
- `200 OK` — triage result returned
- `400 Bad Request` — invalid request shape
- `401 Unauthorized` — missing/invalid auth
- `422 Unprocessable Entity` — semantic validation failed
- `500 Internal Server Error` — unexpected failure
- `504 Gateway Timeout` — execution exceeded timeout budget

---

## 7. GET /sessions/{session_id}

Return the current state of a session and the latest known triage report.

This endpoint is useful for:
- polling,
- debugging,
- resuming UI state,
- reviewing a prior triage result.

### Path params

| Param | Type | Required | Description |
|------|------|----------|-------------|
| `session_id` | string | yes | Session UUID |

### Response

```json
{
  "status": "ok",
  "data": {
    "session_id": "8f8d7d22-1f3e-4e8c-8ca0-4dc4b1d83f29",
    "lifecycle_state": "completed",
    "created_at": "2026-03-20T11:22:00Z",
    "updated_at": "2026-03-20T11:22:14Z",
    "iteration_count": 2,
    "report": {
      "incident_summary": {
        "title": "High 5xx rate",
        "service": "payments-api",
        "severity": "P1"
      },
      "status": "completed",
      "hypotheses": [],
      "next_steps": [],
      "refs": [],
      "safety_notes": [],
      "approval_requests": [],
      "unknowns": []
    }
  },
  "meta": {
    "request_id": "uuid",
    "session_id": "8f8d7d22-1f3e-4e8c-8ca0-4dc4b1d83f29",
    "generated_at": "2026-03-20T11:23:00Z"
  }
}
```

### Response codes
- `200 OK`
- `401 Unauthorized`
- `404 Not Found`

---

## 8. GET /sessions/{session_id}/trace

Return execution trace for a triage session.

This endpoint is intended for:
- observability,
- debugging,
- evaluation,
- demo inspection.

The trace should expose bounded and sanitized execution metadata, not raw unsafe chain-of-thought.

### Path params

| Param | Type | Required | Description |
|------|------|----------|-------------|
| `session_id` | string | yes | Session UUID |

### Response

```json
{
  "status": "ok",
  "data": {
    "session_id": "8f8d7d22-1f3e-4e8c-8ca0-4dc4b1d83f29",
    "trace": [
      {
        "step": 1,
        "type": "planning",
        "status": "completed",
        "started_at": "2026-03-20T11:22:00Z",
        "completed_at": "2026-03-20T11:22:03Z",
        "summary": "Initial investigation plan created"
      },
      {
        "step": 2,
        "type": "tool_call",
        "tool_name": "metrics_tool",
        "status": "completed",
        "started_at": "2026-03-20T11:22:03Z",
        "completed_at": "2026-03-20T11:22:05Z",
        "summary": "Fetched payments-api 5xx and latency metrics"
      },
      {
        "step": 3,
        "type": "analysis",
        "status": "completed",
        "started_at": "2026-03-20T11:22:05Z",
        "completed_at": "2026-03-20T11:22:14Z",
        "summary": "Generated structured triage report"
      }
    ]
  },
  "meta": {
    "request_id": "uuid",
    "session_id": "uuid",
    "generated_at": "2026-03-20T11:23:00Z"
  }
}
```

### Trace exposure rules
- expose step summaries, timings, statuses, tool metadata
- do not expose raw hidden reasoning
- redact secrets, PII, sensitive payload fragments
- allow enough detail for debugging and evals

### Response codes
- `200 OK`
- `401 Unauthorized`
- `404 Not Found`

---

## 9. POST /sessions/{session_id}/approval

Approve or reject a gated action.

This endpoint is used when the triage workflow enters `waiting_approval`.

For the current PoC, this endpoint resolves a gated recommendation and records the human decision in the audit trail. It does not trigger autonomous write execution, because write-capable tools are disabled by default.

### Path params

| Param | Type | Required | Description |
|------|------|----------|-------------|
| `session_id` | string | yes | Session UUID |

### Request

```json
{
  "approval_id": "79ef42c6-d4b8-4f76-a3d5-d4d74d1827b9",
  "decision": "approved",
  "comment": "Rollback is authorized by incident commander"
}
```

### Request fields

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `approval_id` | string | yes | Approval request identifier |
| `decision` | string | yes | `approved` or `rejected` |
| `comment` | string | no | Optional human justification |

### Response

```json
{
  "status": "ok",
  "data": {
    "session_id": "8f8d7d22-1f3e-4e8c-8ca0-4dc4b1d83f29",
    "approval_id": "79ef42c6-d4b8-4f76-a3d5-d4d74d1827b9",
    "decision": "approved",
    "lifecycle_state": "completed",
    "report": {
      "incident_summary": {
        "title": "High 5xx rate",
        "service": "payments-api",
        "severity": "P1"
      },
      "status": "completed",
      "hypotheses": [],
      "next_steps": [],
      "refs": [],
      "safety_notes": [
        {
          "type": "policy",
          "message": "Action was human-approved before continuation",
          "severity": "low"
        }
      ],
      "approval_requests": [],
      "unknowns": []
    }
  },
  "meta": {
    "request_id": "uuid",
    "session_id": "uuid",
    "generated_at": "2026-03-20T11:30:00Z"
  }
}
```

### Response codes
- `200 OK`
- `400 Bad Request`
- `401 Unauthorized`
- `404 Not Found`
- `409 Conflict` — session is not waiting for approval
- `422 Unprocessable Entity` — invalid decision transition

---

## 10. GET /health

Basic health endpoint.

### Response

```json
{
  "status": "ok",
  "data": {
    "service": "agentops-triage-poc",
    "healthy": true,
    "version": "0.1.0"
  },
  "meta": {
    "generated_at": "2026-03-20T11:30:00Z"
  }
}
```

### Notes
This endpoint should remain lightweight and not depend on expensive downstream checks.

### Response codes
- `200 OK`

---

## 11. GET /metrics

Expose service metrics in Prometheus-compatible format.

### Example output

```text
agentops_requests_total 42
agentops_active_sessions 3
agentops_ttfa_seconds_bucket{le="5"} 4
agentops_ttfa_seconds_bucket{le="10"} 19
agentops_tool_success_rate 0.93
agentops_policy_block_total 2
```

### Notes
This endpoint is intended for observability systems, not general client applications.

### Response codes
- `200 OK`

---

## 12. Validation rules

### 12.1 Required fields on incident creation
The following fields are mandatory for `POST /incident`:
- `title`
- `service`
- `severity`
- `timestamp`
- `summary`

### 12.2 Severity constraints
Recommended PoC values:
- `P1`
- `P2`
- `P3`
- `P4`

Unknown values may be:
- rejected,
- or normalized depending on implementation mode.

### 12.3 Input sanitation
User-provided text should be sanitized before:
- prompt construction,
- logging,
- persistence,
- trace exposure.

### 12.4 Size constraints
Recommended PoC limits:
- `title`: <= 200 chars
- `service`: <= 100 chars
- `summary`: <= 4000 chars
- `signals`: <= 50 items
- each signal: <= 300 chars

These may be adjusted later.

---

## 13. Lifecycle semantics

The API should align with the internal session lifecycle.

### Recommended lifecycle states
- `new`
- `validating_input`
- `planning`
- `retrieving`
- `executing_tools`
- `analyzing`
- `waiting_approval`
- `tool_failed`
- `partial_completed`
- `completed`
- `failed`

### Semantics
- `completed` — final report ready
- `partial_completed` — useful report returned with gaps
- `waiting_approval` — blocked pending human decision
- `failed` — system unable to produce safe/useful output

---

## 14. Idempotency and retries

### 14.1 POST /incident
For PoC, idempotency may be omitted initially.

If added later, recommended approaches:
- `Idempotency-Key` header
- incident hash + bounded deduplication window

### 14.2 Approval endpoint
Approvals should be state-aware:
- duplicate approval of already resolved request should return a conflict or safe no-op,
- invalid transitions must not mutate state.

---

## 15. Timeout behavior

The system should use bounded time budgets.

### Recommendations
- request timeout budget for synchronous triage
- per-tool timeout budget
- bounded retries for retriable tool failures
- partial completion instead of hanging indefinitely

### Timeout response example

```json
{
  "status": "error",
  "error": {
    "code": "TIMEOUT",
    "message": "Triage execution exceeded allowed time budget",
    "details": {
      "session_id": "uuid"
    }
  },
  "meta": {
    "request_id": "uuid"
  }
}
```

---

## 16. Safety and policy semantics

### 16.1 Policy-blocked behavior
If the system identifies a blocked operation:
- it must not execute it,
- it must return a safe structured response,
- it should include a `safety_note`,
- it may include `approval_requests`.

### 16.2 Redaction
Sensitive content should be redacted in:
- logs,
- trace output,
- error payloads,
- references when necessary.

### 16.3 Grounding expectation
Claims in `hypotheses` and `next_steps` should be supported by:
- observations,
- retrieved docs,
- or clearly marked uncertainty.

---

## 17. Example minimal happy-path interaction

### 17.1 Create incident

```http
POST /incident
Content-Type: application/json
X-API-Key: demo-key
```

```json
{
  "title": "Latency spike after deploy",
  "service": "checkout-api",
  "severity": "P2",
  "timestamp": "2026-03-20T12:05:00Z",
  "summary": "p95 latency tripled after release 2026.03.20-4",
  "signals": [
    "p95 latency up 3x",
    "error rate stable"
  ],
  "environment": "prod"
}
```

### 17.2 Receive report

```json
{
  "status": "ok",
  "data": {
    "session_id": "uuid",
    "report": {
      "incident_summary": {
        "title": "Latency spike after deploy",
        "service": "checkout-api",
        "severity": "P2"
      },
      "status": "completed",
      "hypotheses": [
        {
          "id": "uuid",
          "statement": "Recent release likely increased response latency without causing immediate failures",
          "confidence": 0.77,
          "status": "active",
          "supporting_refs": [
            "obs:metrics-1"
          ]
        }
      ],
      "next_steps": [
        {
          "priority": 1,
          "action": "Compare slow endpoints before and after the deploy",
          "rationale": "Needed to localize performance regression",
          "requires_approval": false
        }
      ],
      "refs": [
        {
          "id": "obs:metrics-1",
          "type": "observation",
          "source": "metrics_tool",
          "title": "checkout-api latency",
          "snippet": "p95 rose from 180ms to 560ms after deploy"
        }
      ],
      "safety_notes": [],
      "approval_requests": [],
      "unknowns": []
    }
  },
  "meta": {
    "request_id": "uuid",
    "session_id": "uuid",
    "generated_at": "2026-03-20T12:05:12Z"
  }
}
```

---

## 18. Future API extensions

The following are intentionally deferred but compatible with this design:
- async execution with `202 Accepted`
- streaming progress updates
- bulk eval execution endpoints
- session cancellation endpoint
- tool registry endpoints
- admin/audit endpoints
- multi-tenant auth model

---

## 19. Definition of done

The API spec is considered implementation-ready when:
- all required endpoints are defined,
- request/response schemas are stable,
- common error model is fixed,
- lifecycle semantics are documented,
- safety/approval behavior is explicit,
- backend engineers can implement handlers without major ambiguity.