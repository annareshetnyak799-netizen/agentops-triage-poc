# PoC: AgentOps — агент для триажа инцидентов и безопасных действий (System Design Project)

## 1) Контекст и проблема
В инженерных командах (SRE/DevOps/Platform) значительная часть времени уходит на первичный триаж инцидентов:
- собрать симптомы из алертов, логов, метрик
- найти релевантный runbook/документацию
- предложить гипотезу и план действий
- выполнить 1–2 безопасных диагностических шага (или подготовить команды)

Это повторяющаяся задача с высокой ценой ошибки (опасные команды, утечки данных, неверные действия).

## 2) Цель PoC
Собрать PoC **агентной системы**, которая по входному инциденту:
1) агрегирует сигналы (алерт + метрики/логи) через инструменты (API),
2) достаёт знания из внешней базы (runbooks),
3) ведёт **сессионное состояние и память**,
4) предлагает структурированный план (RCA гипотезы + next steps),
5) выполняет только **безопасные** действия (read-only / sandbox / approval).

> Важно: если это можно реализовать “простым чатом”, проект не подходит — здесь обязателен tool-use, память, знания, мониторинг и safety-гейт.

## 3) Пользователи и сценарии (User Stories)
### Основные
- **SRE on-call**: “У меня пришёл алерт. Хочу за 1 минуту понять: что сломалось, где смотреть, что сделать первым”.
- **Инженер**: “Хочу найти релевантный runbook и конкретные команды/дашборды”.
- **Тимлид/постмортем**: “Хочу видеть, что агент делал, и оценить качество/точность”.

### Дополнительные
- “У меня нет доступа к prod-командам — агент должен предложить действия, но требовать подтверждение”.

## 4) Метрики успеха (Success Metrics)
PoC считается успешным, если на тестовом наборе инцидентов:
- **Triage Time**: время до выдачи first-action plan ≤ 30 секунд (p95).
- **Accuracy**:
  - Top-1 классификация типа инцидента ≥ 60% (на маленьком наборе, честно измеряем).
  - План действий содержит ≥ 3 корректных next steps в ≥ 70% кейсов (manual eval rubric).
- **Safety**:
  - 0 случаев утечки PII в ответах (на тестах с PII).
  - 0 случаев выполнения write/опасных действий без approval.
- **Операционные**:
  - Доля tool-calls, завершившихся ошибкой ≤ 10% (с retry/fallback).

## 5) Ограничения и предположения (Operational Constraints)
- Ограничение времени ответа: p95 ≤ 30s.
- Лимит стоимости: ≤ X токенов/запрос (конфигом).
- Ограничения доступа: часть инструментов может быть недоступна (403/timeout).
- Источники правды: алерты/метрики/логи/KB. Агент не должен “выдумывать” факты.

## 6) Область (Scope) и вне области (Non-goals)
### In Scope (PoC)
- 1–2 источника метрик (например, Prometheus API mock / JSON fixtures)
- 1 источник логов (Loki/ELK mock / файлы)
- KB runbooks (Markdown папка или простая RAG-коллекция)
- Оркестрация: multi-step agent loop (plan → tool → observe → decide)
- Память: session memory + short-term summary + “known incidents” cache
- Safety layer: PII redaction + tool policy + approval flow
- Мониторинг: логи, трейсинг шагов, метрики tool errors, latency
- Evals: набор тест-кейсов + рубрика оценивания

### Non-goals
- Полная интеграция с реальным продом/секретами
- Автоматическое применение remediation в инфраструктуре без человека
- 100% точность RCA

## 7) Высокоуровневая архитектура
Компоненты:
1. **API Gateway / UI** (CLI или простой HTTP endpoint)
   - POST `/incident` → старт сессии
   - GET `/sessions/{id}` → статус/история
2. **Orchestrator (Agent Core)**
   - Planner / Router
   - Tool Executor (с policy)
   - State Manager (session store)
3. **Tools / Integrations**
   - MetricsTool: query metrics (read-only)
   - LogsTool: query logs (read-only)
   - KBTool: search runbooks (RAG / BM25 / hybrid)
   
  Канонические implementation-level идентификаторы инструментов:
   - `MetricsTool` → `metrics_tool`
   - `LogsTool` → `logs_tool`
   - `KBTool` → `runbook_retrieval_tool`

4. **Knowledge Base**
   - Runbooks, FAQ, “known issues”
5. **State & Memory**
   - Session state (steps, observations, decisions)
   - Summaries (для длинных сессий)
   - Optional: incident embeddings cache
6. **Safety Layer**
   - PII scrubber (до логирования и до ответа)
   - Tool policy (allow/denylist; read-only by default)
   - Approval workflow (human-in-the-loop)
7. **Observability**
   - structured logs (JSON)
   - metrics: latency, tool_error_rate, safety_blocks
   - traces: шаги агента (span per step)
8. **Eval Harness**
   - dataset инцидентов
   - автопрогон + отчёт

## 8) Функциональные требования (Functional Requirements)
### FR-1. Приём инцидента
Система принимает инцидент с минимальным каноническим набором полей:
- `title`, `service`, `severity`, `timestamp`, `summary`
- опционально `signals`
- опционально `environment`, `reporter`
- опционально `alert_payload` и `links` как расширения входного контракта

### FR-2. Планирование и разбор
Агент обязан:
- сформировать гипотезы (не более N)
- сформировать план next steps (структурированно)
- явно указывать источники наблюдений (tool outputs / KB refs)

### FR-3. Tool-use
Агент вызывает инструменты только через Tool Executor:
- retries с backoff на transient ошибки
- timeout на каждый tool-call
- логирование входов/выходов (с редактированием PII)

### FR-4. Knowledge retrieval
Система должна извлекать релевантные runbooks:
- по service + сигнатурам (error message / metric spikes)
- возвращать 3–5 релевантных фрагментов

### FR-5. State & memory
Для каждой сессии хранится:
- история шагов (plan → action → observation)
- краткое summary (обновляется каждые K шагов)
- финальный отчёт (RCA guess + actions + todo)

### FR-6. Safety (обязательно)
- До выдачи ответа: PII redaction (email/phone/паспорт/карта — минимум)
- Опасные инструменты (shell/write/delete) по умолчанию запрещены
- Любой “изменяющий” шаг требует `approval=true` (ручного подтверждения)

### FR-7. Отчёт
Агент возвращает:
- `incident_type`, `confidence`
- `hypotheses[]`
- `next_steps[]` (с приоритетом)
- `tools_used[]`
- `kb_refs[]`
- `safety_notes[]`

## 9) Нефункциональные требования (Non-functional Requirements)
- Надёжность: graceful degradation при падении tools/KB
- Наблюдаемость: корреляция по `session_id`
- Безопасность: не хранить сырые PII в логах
- Тестируемость: все инструменты имеют mock режим и фикстуры

## 10) Edge-cases (ошибки и failover)
Система должна корректно обрабатывать:
- tool timeout / 5xx → retry → fallback на KB-only режим
- пустые/шумные логи → запрос уточняющих данных у пользователя
- конфликтные сигналы (метрики ок, алерт горит) → выдать ветвление гипотез
- попытка агента выполнить запрещённое действие → блок + объяснение

## 11) Evals (оценка качества)
Минимальный набор:
- 10–20 синтетических инцидентов (fixtures)
- Rubric (0–2 балла за пункт):
  - корректность классификации
  - релевантность runbook
  - качество next steps
  - наличие ссылок на источники
  - соблюдение safety
Выход: `eval_report.md` + метрики + примеры провалов.

## 12) Форматы данных (черновик)

### Incident (input)
Канонический контракт входного инцидента для реализации зафиксирован в `docs/API_SPEC.md`.

Поля `alert_payload` и `links` рассматриваются как опциональные расширения и могут быть опущены в минимальном PoC-сценарии.

```json
{
  "title": "High 5xx rate",
  "service": "payments-api",
  "severity": "P1",
  "timestamp": "2026-02-22T10:00:00Z",
  "summary": "Error rate increased after deploy",
  "signals": [
    "5xx > 12%",
    "latency p95 up 3x"
  ],
  "environment": "prod",
  "reporter": "oncall-engineer",
  "alert_payload": {
    "labels": {},
    "annotations": {}
  },
  "links": [
    "https://.../dashboard"
  ]
}
```



