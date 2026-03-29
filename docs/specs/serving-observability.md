# Serving and Observability Spec

## Purpose

Этот документ фиксирует minimal runtime model, configuration policy и observability requirements для AgentOps Triage PoC как сервиса.

## Runtime Modes

Поддерживаемые режимы PoC:
- `local` — локальная разработка и ручной прогон;
- `demo` — демонстрационный запуск с bounded integrations;
- `offline_eval` — пакетный прогон fixtures и сбор eval artifacts.

## Serving Model

PoC работает как HTTP JSON service с session-oriented execution.

Базовый execution model:
- `POST /incident` запускает triage session;
- исполнение по умолчанию synchronous, если укладывается в bounded latency budget;
- session state and trace доступны через read endpoints;
- approval decision приходит отдельным endpoint.

## Configuration

Runtime configuration должна задавать:
- model / provider;
- default tool timeout;
- session time budget;
- max tool calls;
- retry policy;
- token or cost budget;
- write-tools policy;
- observability settings.

Минимальные PoC assumptions:
- `write_tools_enabled = false`
- bounded retries only for transient failures
- partial completion preferred over long-running stuck execution

## Secrets Policy

Для PoC:
- production secrets не используются;
- реальные integrations необязательны;
- при добавлении интеграций используются read-only credentials with least privilege.

Secrets не должны попадать:
- в structured logs;
- в traces;
- в final report;
- в stored raw payloads.

## Health Semantics

### Liveness
Процесс запущен и способен обслуживать базовые internal operations.

### Readiness
Сервис готов принимать новые requests и может создать новую session.

### Degraded readiness
Часть зависимостей недоступна, но сервис всё ещё способен:
- принять incident;
- выполнить bounded triage;
- вернуть `partial_completed` или `waiting_approval`.

## Operational Limits

Канонические PoC limits:
- `p95 TTFA <= 30s`
- `max_tool_calls <= 6`
- default `tool_timeout_s = 3`
- bounded `time_budget_s = 30`
- bounded retries for transient failures
- bounded context / summarization policy

Если отдельный dependency имеет больший hard timeout, orchestrator всё равно обязан уважать общий session budget.

## Observability

### Structured logs
Минимальные поля:
- `ts`
- `level`
- `session_id`
- `step_type`
- `tool_name`
- `status`
- `latency_ms`
- `error_type`
- `fallback_used`
- `safety_event_type`

### Metrics
Минимальный набор:
- `ttfa_ms`
- `end_to_end_latency_ms`
- `tool_calls_total`
- `tool_calls_failed`
- `fallback_total`
- `policy_blocks_total`
- `pii_redactions_total`
- `llm_calls_total`
- `llm_calls_failed`
- `degraded_sessions_total`
- `session_budget_exhausted_total`

### Tracing
- one trace per session;
- one span per major orchestration step;
- child spans per tool call.

## Eval Signals

Runtime and quality checks для PoC:
- TTFA
- tool success rate
- fallback correctness
- policy violation rate
- PII leakage rate
- degraded session rate

## Failure and Degradation Policy

При runtime problems сервис должен:
- fail fast on invalid input;
- retry only bounded transient failures;
- degrade gracefully when tools or KB are unavailable;
- return `partial_completed` if safe useful result exists;
- avoid hanging sessions beyond configured budget.

## Persistence Guidance

Сохраняются:
- session state;
- tool-call metadata;
- observations;
- safety events;
- approval requests;
- final report;
- structured telemetry metadata.

Не сохраняются по умолчанию:
- raw unredacted logs;
- secrets;
- unbounded prompt context.

## Out of Scope

Для текущего PoC не требуются:
- production-grade autoscaling;
- complex multi-tenant isolation;
- asynchronous worker fleet;
- production incident-response automation.

