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

## Traffic Control and Efficiency

Для PoC достаточно простых runtime controls:
- bounded concurrency на уровне HTTP service;
- rate limiting на входящие triage requests;
- no batching by default, так как PoC ориентирован на interactive incident triage, а не bulk inference;
- retrieval и tool responses могут кэшироваться краткоживущим in-memory cache по `(service, query, time_range)` в рамках одной session или короткого окна.

Цель этих механизмов:
- не перегружать внешние зависимости;
- не создавать cascading failures при burst traffic;
- удерживать latency и cost в пределах bounded execution model.

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

## Dashboard Layout

Для PoC достаточно одного operational dashboard с четырьмя зонами:
1. **Latency**
   - TTFA p50 / p95
   - end-to-end latency p50 / p95

2. **Dependency health**
   - tool failure rate
   - LLM failure rate
   - degraded session rate

3. **Safety**
   - policy blocks
   - PII redactions
   - approval requests

4. **Execution quality**
   - tool success rate
   - fallback usage
   - budget exhaustion count

## Example Alert Rules

Примерные alert thresholds для PoC:
- `TTFA p95 > 30s` в течение 15 минут
- `tool_calls_failed / tool_calls_total > 0.1` в течение 15 минут
- `llm_calls_failed / llm_calls_total > 0.1` в течение 15 минут
- `degraded_sessions_total` заметно выше baseline
- `policy_blocks_total > 0` ожидаемо допустимо, но требует review
- `PII leakage > 0` считается критическим дефектом

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

## Graceful Shutdown

При остановке сервиса expected behavior такой:
- новые sessions больше не принимаются;
- активным sessions даётся bounded grace period на завершение;
- если session не успела завершиться, в persistence сохраняется последний безопасный state и trace metadata;
- после рестарта сервис может либо восстановить session из persisted state, либо явно пометить её как interrupted / failed depending on implementation mode.

## CI / CD and LLMOps Gate

Для текущего PoC достаточно лёгкого pipeline, который проверяет изменения в prompts, config и eval artifacts перед merge:

1. **Static checks**
- markdown/docs lint
- schema sanity checks
- basic config validation

2. **Quality checks**
- regression eval run на фиксированных fixtures
- проверка safety scenarios: PII, injection, policy violation, tool outage

3. **Review gate**
- manual review для изменений prompt templates, runtime limits и safety policy
- merge в основную ветку только после успешного прохождения eval regression

4. **Deployment strategy for PoC**
- ручной rollout в `main`
- без сложного staged deployment

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

