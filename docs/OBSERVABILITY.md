# OBSERVABILITY — logs/metrics/traces (AgentOps Triage PoC)

## 1) Structured logs (JSON)

Обязательные поля:
- `ts`
- `level`
- `session_id`
- `step_type`
- `tool_name` (если это tool call)
- `status`
- `latency_ms`
- `error_type`
- `fallback_used` (bool)
- `safety_event_type` (если было)
- `ttfa_ms` (на шаге report)

Правило:
- никаких raw PII / secrets;
- только sanitized payload summaries и metadata;
- все логи должны коррелироваться по `session_id`.

## 2) Metrics (минимум)

### Session and latency
- `ttfa_ms` histogram (p50/p95)
- `end_to_end_latency_ms` histogram
- `degraded_sessions_total` counter
- `session_budget_exhausted_total` counter

### Tools and dependencies
- `tool_calls_total` counter
- `tool_calls_failed` counter
- `fallback_total` counter
- `llm_calls_total` counter
- `llm_calls_failed` counter

### Safety
- `policy_blocks_total` counter
- `pii_redactions_total` counter
- `approval_requests_total` counter

## 3) Tracing (минимум)

- one trace per session
- one span per major step:
  - `validate`
  - `plan`
  - `retrieve`
  - `tool`
  - `analyze`
  - `safety`
  - `report`
- child span per tool call

## 4) Health and degraded mode

Наблюдаемость должна различать:
- `liveness`: процесс запущен;
- `readiness`: сервис может принимать новые requests;
- `degraded readiness`: часть зависимостей недоступна, но partial triage всё ещё возможен.

## 5) Alerting (PoC, опционально)

- tool failure rate > X%
- LLM failure rate > X%
- TTFA p95 > target
- degraded session rate > expected threshold
- policy violations > 0
- PII leakage > 0
