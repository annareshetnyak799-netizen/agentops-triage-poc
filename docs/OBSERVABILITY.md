# OBSERVABILITY — logs/metrics/traces (AgentOps Triage PoC)

## 1) Structured logs (JSON)
Обязательные поля:
- `ts`, `level`, `session_id`, `step_type`
- `tool_name` (если tool_call), `status`, `latency_ms`, `error_type`
- `fallback_used` (bool)
- `safety_event_type` (если было)
- `ttfa_ms` (на шаге report)

Правило: никаких raw PII / secrets.

## 2) Metrics (минимум)
- `ttfa_ms` histogram (p50/p95)
- `end_to_end_latency_ms` histogram
- `tool_calls_total` counter
- `tool_calls_failed` counter
- `fallback_total` counter
- `policy_blocks_total` counter
- `pii_redactions_total` counter

## 3) Tracing (минимум)
- trace per session
- span per step: plan/tool/observe/decide/report
- child span per tool call

## 4) Alerting (PoC, опционально)
- tool failure rate > X%
- TTFA p95 > target
- policy violations > 0 (должно быть 0)