# System Design — AgentOps Triage PoC

## 1. Purpose and Scope

AgentOps Triage PoC — это сервис для первичного triage инцидентов, который по входному incident payload собирает контекст из read-only источников, извлекает релевантные runbooks, формирует hypotheses и next steps и возвращает структурированный отчёт с refs и safety notes.

Цель PoC:
- сократить время до первого структурированного плана triage;
- стандартизировать первичный разбор инцидентов;
- снизить риск unsafe действий и утечек данных;
- дать наблюдаемую и воспроизводимую execution model перед началом реализации.

В scope PoC:
- HTTP API для запуска triage-сессии и просмотра её состояния;
- bounded orchestration loop `plan -> retrieve -> tool -> analyze -> decide`;
- read-only integrations для метрик, логов и runbooks;
- session state, short-term memory и structured trace;
- safety layer: redaction, tool policy, approval checkpoint;
- observability: logs, metrics, traces;
- eval-driven проверка качества и graceful degradation.

Вне scope PoC:
- production secrets и реальные write-capable integrations;
- автоматическое remediation в инфраструктуре;
- полноценный UI;
- долгосрочная multi-tenant memory;
- гарантированное RCA.

---

## 2. Key Architectural Decisions

1. **Session-oriented execution**  
   Каждый incident создаёт отдельную bounded session с явным lifecycle state и trace.

2. **Read-only by default**  
   Все интеграции в PoC работают только в режиме чтения. Write-capable tools отключены.

3. **Partial completion is valid**  
   Если данных недостаточно или зависимости недоступны, система возвращает `partial_completed`, а не зависает и не “додумывает” ответ.

4. **Evidence before conclusion**  
   Hypotheses и next steps должны опираться на tool outputs, retrieval refs или явно зафиксированную неопределённость.

5. **Bounded runtime**  
   У сессии есть time budget, limit на tool calls, bounded retries и ограничение контекста.

6. **Safety before response**  
   Перед возвратом отчёта выполняются redaction, policy checks и validation of groundedness.

7. **Observability-first design**  
   Каждая сессия должна быть inspectable по `session_id` через structured logs, metrics и traces.

8. **Mock-friendly integrations**  
   PoC строится на fixtures/mocks, чтобы обеспечить воспроизводимость и eval coverage.

---

## 3. System Modules

### 3.1 API Layer
Отвечает за приём incident payload, создание session, возврат текущего статуса, trace и approval decision.

Основные endpoints:
- `POST /incident`
- `GET /sessions/{session_id}`
- `GET /sessions/{session_id}/trace`
- `POST /sessions/{session_id}/approval`
- `GET /health`
- `GET /metrics`

### 3.2 Orchestrator
Ядро системы, которое управляет lifecycle session, планирует шаги, вызывает retrieval/tools, собирает observations, обновляет hypotheses и строит final report.

### 3.3 Retrieval Layer
Извлекает релевантные runbooks и KB snippets по service, summary и observed signals. Retrieval является вспомогательным контуром: если он недоступен, triage продолжается без KB при возможности.

### 3.4 Tool Layer
Предоставляет нормализованный интерфейс к read-only integrations:
- `metrics_tool`
- `logs_tool`
- `runbook_retrieval_tool`

Опциональные инструменты для следующих этапов:
- `service_catalog_tool`
- `deployment_tool`
- `incident_history_tool`

### 3.5 Session State and Persistence
Хранит incident input, lifecycle state, tool-call metadata, observations, hypotheses, next steps, safety events, approval requests и final report.

### 3.6 Safety and Policy Layer
Отвечает за:
- PII redaction;
- tool allowlist / denylist;
- approval gating;
- запрет следования инструкциям из недоверенных данных;
- проверку safe response semantics.

### 3.7 Observability Layer
Собирает:
- structured logs;
- metrics;
- traces;
- safety and degradation events.

### 3.8 Eval Harness
Нужен для воспроизводимой оценки качества, reliability и safety на фиксированных fixtures.

---

## 4. Main Workflow

Базовый synchronous PoC flow:

1. Клиент вызывает `POST /incident`.
2. API валидирует вход и создаёт `session_id`.
3. Session переходит в `validating_input`.
4. Orchestrator строит initial plan и определяет, нужен ли retrieval и какие tools вызывать.
5. Retrieval layer извлекает top-k runbook snippets.
6. Tool layer собирает live evidence из metrics/logs.
7. Orchestrator нормализует observations, обновляет hypotheses и ранжирует next steps.
8. Safety layer выполняет redaction и policy checks.
9. Система возвращает один из исходов:
   - `completed`
   - `partial_completed`
   - `waiting_approval`
   - `failed`

Approval flow:
- если анализ выявил gated recommendation, session переходит в `waiting_approval`;
- `POST /sessions/{session_id}/approval` фиксирует human decision;
- в текущем PoC approval не запускает autonomous write execution, а только закрывает audit/control point, поскольку write-capable tools отключены.

---

## 5. State, Memory and Context Handling

### 5.1 Lifecycle State
Канонические lifecycle states:
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

Lifecycle state — главный источник истины для orchestration flow.

### 5.2 Session State
В session state сохраняются:
- normalized incident input;
- current lifecycle state;
- iteration count;
- selected tools and tool-call metadata;
- observations;
- hypotheses;
- next steps;
- safety events;
- approval requests;
- final report.

### 5.3 Memory
Memory в PoC ограничена short-term session memory:
- rolling summary;
- known facts;
- список уже выполненных шагов и observed evidence.

Долгосрочная organizational memory в scope PoC не входит.

### 5.4 Context Policy
Контекст для LLM строится из:
- normalized incident input;
- rolling summary;
- relevant observations;
- retrieval snippets;
- bounded tool results.

При превышении context budget:
- длинные outputs summarization/truncation;
- raw logs в prompt не передаются целиком;
- недоверенные данные предварительно sanitization;
- при сильном budget pressure система предпочитает `partial_completed` или запрос недостающих данных.

---

## 6. Retrieval Design

### 6.1 Sources
Источники retrieval в PoC:
- markdown runbooks;
- known issues / FAQ;
- опционально postmortem snippets.

### 6.2 Query Inputs
Retrieval query строится из:
- `service`
- `summary`
- `signals`
- ключевых сигнатур из логов или алертов

### 6.3 Output
Retrieval возвращает:
- `top_k = 3..5` snippets;
- refs на документы;
- краткий normalized summary retrieved context.

### 6.4 Retrieval Strategy
Базовая стратегия PoC:
- lexical/BM25-like or simple keyword retrieval;
- service-aware filtering;
- no mandatory reranking requirement для первой реализации.

### 6.5 Fallback
Если retrieval:
- не вернул релевантных документов, система продолжает triage на tools/live evidence;
- недоступен, система не блокируется и идёт в degraded flow без KB;
- вернул потенциально инъекционный контент, этот контент рассматривается как untrusted input и не меняет policy.

---

## 7. Tools and API Integrations

### 7.1 Canonical Tool Names
Для реализации используются канонические идентификаторы:
- `metrics_tool`
- `logs_tool`
- `runbook_retrieval_tool`

Logical names в high-level документах:
- `MetricsTool` -> `metrics_tool`
- `LogsTool` -> `logs_tool`
- `KBTool` -> `runbook_retrieval_tool`

### 7.2 Common Tool Contract
Каждый tool:
- принимает structured input;
- возвращает structured success/error envelope;
- имеет normalized error model;
- логирует только sanitized metadata;
- работает в bounded execution model.

### 7.3 Access Mode
Все tools в PoC:
- read-only;
- no autonomous side effects;
- no shell / delete / patch / restart / scale actions.

### 7.4 Timeout and Retry Model
- у orchestration есть общий session time budget;
- у каждого tool есть hard timeout;
- transient failures допускают bounded retry;
- invalid arguments не ретраятся;
- при исчерпании budget система завершает session в degraded mode.

### 7.5 External Dependencies
Основные dependency classes:
- LLM provider
- metrics backend
- logs backend
- KB storage
- observability backend

PoC рассчитан на mock/fixture mode, поэтому реальные production integrations не требуются для демонстрации дизайна.

---

## 8. Failure Modes, Fallbacks and Guardrails

### 8.1 Tool Timeout or Outage
Сценарий:
- metrics/logs backend отвечает timeout/403/5xx

Поведение:
- bounded retry на transient ошибки;
- фиксация failure metadata;
- переход в `tool_failed` или сразу в degraded analysis;
- возврат `partial_completed`, если полезный ответ всё ещё возможен.

### 8.2 Retrieval Returned Nothing
Сценарий:
- KB не нашла релевантные runbooks

Поведение:
- triage продолжается по live evidence;
- в report добавляется uncertainty/unknowns;
- система не выдумывает KB refs.

### 8.3 LLM or Provider Failure
Сценарий:
- timeout, rate limit, 5xx, provider unavailable

Поведение:
- bounded retry только для retriable failures;
- при повторном сбое — `failed` или `partial_completed`, если уже собрано достаточно evidence;
- no infinite retry loops.

### 8.4 Conflicting or Insufficient Evidence
Сценарий:
- сигналы противоречат друг другу или их недостаточно

Поведение:
- несколько hypotheses со сниженным confidence;
- явная фиксация unknowns;
- safe next steps вместо категоричных выводов.

### 8.5 Policy-Blocked Recommendation
Сценарий:
- next step относится к risky or write-like action

Поведение:
- action не исполняется;
- создаётся approval request;
- session переходит в `waiting_approval`.

### 8.6 Budget Exhaustion
Сценарий:
- исчерпан time budget, tool-call budget или token budget

Поведение:
- остановка дальнейшего исследования;
- возврат лучшего доступного safe result;
- финальный статус `partial_completed`.

### 8.7 Prompt Injection / Unsafe Instructions
Сценарий:
- вредные инструкции приходят из logs, KB или user input

Поведение:
- эти данные считаются untrusted;
- система не исполняет инструкции из данных;
- policy и cite-or-ask остаются выше retrieved content.

---

## 9. Operational Limits

Для PoC фиксируются следующие ограничения:
- `p95 TTFA <= 30s`
- `max_tool_calls <= 6`
- `tool_timeout_s = 3` как default orchestration target
- `time_budget_s = 30` на session
- `max_retries = 2` только для transient failures
- bounded context / summarization policy
- `write_tools_enabled = false`
- лимит токенов и стоимости задаётся конфигом модели и считается частью bounded execution

Если отдельный tool имеет больший hard timeout, orchestration всё равно обязана уважать общий session budget и завершать flow через degraded result при необходимости.

---

## 10. Observability and Control Points

### 10.1 Structured Logs
Логи должны быть:
- JSON structured;
- коррелируемы по `session_id`;
- без raw PII и secrets;
- пригодны для отладки execution path.

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

### 10.2 Metrics
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

### 10.3 Tracing
- one trace per session;
- one span per major step;
- child spans for tool calls.

### 10.4 Control Points
Ключевые точки контроля:
- input validation;
- tool policy enforcement;
- response redaction;
- approval checkpoint;
- budget checks;
- trace/log persistence;
- eval coverage on risky scenarios.

### 10.5 Health Model
- `liveness`: процесс запущен;
- `readiness`: сервис может принимать новые requests;
- `degraded readiness`: часть зависимостей недоступна, но partial triage всё ещё возможен.

---

## 11. Open Issues

1. Нужно ли в первой реализации поддерживать только synchronous flow, или сразу предусмотреть async mode с polling как extension?
2. Какие optional tools реально попадут в первую итерацию реализации, кроме `metrics_tool`, `logs_tool` и `runbook_retrieval_tool`?
3. Где физически хранить session trace и large raw outputs: inline, file refs или object storage refs?
4. Должен ли `FinalReport` versioning быть append-only или достаточно latest-only в PoC?
5. Какой минимальный набор eval fixtures обязателен до начала coding phase, чтобы проверить degraded paths и safety invariants?

---

## 12. Related Documents

- `docs/ARCHITECTURE.md`
- `docs/API_SPEC.md`
- `docs/DATA_MODEL.md`
- `docs/STATE_MACHINE.md`
- `docs/STATE_MEMORY.md`
- `docs/TOOLS_CONTRACTS.md`
- `docs/KB_SPEC.md`
- `docs/OBSERVABILITY.md`
- `docs/EVALS.md`
- `docs/GOVERNANCE.md`
- `docs/CONFIG.md`

