# AgentOps Triage PoC
**Агентная система для триажа инцидентов:** автоматически собирает сигналы через инструменты (метрики/логи), находит релевантные runbooks в базе знаний, ведёт сессионную память и выдаёт безопасный план действий.

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](#)
[![Status](https://img.shields.io/badge/status-PoC-orange.svg)](#)

> **Зачем это бизнесу:** меньше простой и дешевле on-call.  
> Система сокращает **время до первого плана действий (TTFA / time-to-first-action)** и помогает снижать **MTTR** за счёт автоматизированного сбора контекста (alerts/metrics/logs), ссылок на источники и **safety-гейта** (PII redaction, tool allowlist, approval).

**Проблема:** в on-call контекст размазан по алертам, дашбордам, логам и runbooks; triage занимает время, а цена ошибки высока (unsafe действия, утечки PII, неверные гипотезы).

---

## Почему это агентная система (а не чат)
В “простом чате” инженер сам решает, **что** дергать (какие метрики/логи), **в каком порядке** и **как интерпретировать** результаты.  
Здесь агент **самостоятельно** выполняет цикл `plan → tool → observe → decide`:
- строит гипотезы и план проверок,
- выбирает инструменты и параметры запросов,
- интерпретирует результаты, обновляет план и приоритеты,
- завершает triage структурированным отчётом.

Человек подключается только в точках **approval**, если предлагаются потенциально рискованные действия.

**Про “стандартизацию” и стохастичность LLM:** мы стандартизируем процесс и формат результата (структура отчёта, policy, approval), а воспроизводимость усиливаем конфигом (низкая temperature), лимитами tool-calls и evals на фиксированных fixtures.

---

## Бизнес-ценность и KPI (эффективность)
Система снижает стоимость инцидентов и нагрузку на on-call за счёт ускорения первичного triage и снижения риска ошибочных действий.

**Кому полезно**
- **SRE/DevOps on-call:** быстрее понять “что происходит и что делать дальше”
- **Платформа/тимлид:** меньше эскалаций и ручной рутины, единый процесс triage
- **Бизнес:** быстрее восстановление сервиса и меньше потерь от деградаций

**Где это даёт эффект**
- **Внешние (customer-facing) сервисы:** меньше простоя → меньше потерь выручки/SLA штрафов и репутационных рисков.
- **Внутренние сервисы:** меньше потерь инженерного времени и задержек процессов (CI/CD, биллинг, аналитика), меньше переключения контекста и эскалаций.

**Почему safety-гейт — это ценность**
- предотвращает “secondary incidents”: неверные команды/действия в проде могут усугубить сбой;
- снижает риск утечек (PII/токены) в чат/логи;
- делает внедрение поэтапным: сначала рекомендации, затем read-only диагностика, затем действия только через approval.

---

## Метрики успеха (PoC)
> Подробные определения и правила подсчёта: [`docs/METRICS.md`](docs/METRICS.md)

**Определения (кратко)**
- **TTFA (time-to-first-action):** время от получения инцидента системой до выдачи агентом **первого структурированного плана действий** (hypotheses + top-3 next steps). Это метрика скорости triage со стороны системы, не зависит от реакции человека.
- **MTTR:** время от начала деградации сервиса до восстановления SLO. В PoC MTTR обычно выступает как **бизнес-цель**, на которую мы влияем через ускорение triage.

**Targets (PoC)**
- **p95 TTFA ≤ 30s**  
  *Target относится к PoC-условиям: `max_tool_calls ≤ 6`, `tool_timeout ≤ 3s`, read-only tools, ограничение контекста.*
- **Plan Quality Pass Rate ≥ 70%** (порог “pass” по рубрике из `docs/EVALS.md`)
- **Precision@3 next steps ≥ 0.7**
- **Tool success rate ≥ 90%**
- **0 утечек PII** в ответах и логах на PII-тестах
- **0 нарушений политики инструментов** (опасные действия без approval)
- **≤ 10% ошибок tool-call** (retry + fallback)

**Как считаем (коротко)**
- `TTFA = t(first_response_with_plan) - t(incident_received)`
- `Tool success rate = successful_calls / total_calls`
- `PII leakage rate`: прогоняем ответы/логи через детекторы (regex email/phone/token + “canary” строки), цель: 0 совпадений.

---

## Что покажем на демо (PoC)
На демо будет 3–4 сценария **с трассировкой шагов агента** `plan → tool → observe → decide` (без ручного выбора инструментов человеком):
1) **Нормальный инцидент:** алерт → agent вызывает tools (metrics/logs) → находит runbook → выдаёт план (hypotheses + next steps) со ссылками на источники.
2) **Tools недоступны (timeout/403):** agent делает retry/fallback → деградирует в KB-only режим и запрашивает недостающие данные.
3) **Safety кейс (PII/injection):** данные маскируются, попытки unsafe действий блокируются (approval required).
4) **Неопределённость:** данных недостаточно/сигналы конфликтуют → агент формирует 2–3 гипотезы, явно отмечает ограничения и задаёт уточняющие вопросы (вместо “догадок”).

---

## Что НЕ делает PoC (out-of-scope)
- Не выполняет remediation/изменяющие действия в production автоматически (no auto-write).
- Не работает с production-секретами и реальными доступами (на PoC используются fixtures/mocks).
- Не гарантирует 100% точность RCA: выдаёт гипотезы и первые шаги triage.
- Не предоставляет полноценный UI: достаточно CLI или минимального HTTP API.

---

## Документация

Проект включает продуктовые, governance и implementation-oriented документы, которые вместе образуют пакет системного дизайна PoC.

### Основной документ Milestone 2
- [`docs/SYSTEM-DESIGN.md`](docs/SYSTEM-DESIGN.md) — сводный системный дизайн PoC: архитектурные решения, модули, workflow, state/memory, retrieval, integrations, failure modes, guardrails и operational limits

### Продукт и правила работы системы
- [`docs/PRODUCT-PROPOSAL.md`](docs/PRODUCT-PROPOSAL.md) — идея проекта, метрики, сценарии, ограничения, архитектура и data flow
- [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md) — risk register, политика логов и PII, защита от prompt injection, approval workflow
- [`docs/METRICS.md`](docs/METRICS.md) — метрики качества PoC
- [`docs/EVALS.md`](docs/EVALS.md) — методика оценивания и формат отчёта

### Проектная документация для реализации
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — общая архитектура системы и зоны ответственности компонентов
- [`docs/API_SPEC.md`](docs/API_SPEC.md) — внешний API-контракт системы
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — доменные сущности и связи между ними
- [`docs/TOOLS_CONTRACTS.md`](docs/TOOLS_CONTRACTS.md) — контракты инструментов, их интерфейсы и границы безопасности
- [`docs/STATE_MACHINE.md`](docs/STATE_MACHINE.md) — жизненный цикл сессии и модель переходов между состояниями
- [`docs/STATE_MEMORY.md`](docs/STATE_MEMORY.md) — политика state/memory и summarization
- [`docs/KB_SPEC.md`](docs/KB_SPEC.md) — retrieval-контур и формат базы знаний
- [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md) — логи, метрики, трейсы и degraded-mode observability
- [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) — активы, trust boundaries, угрозы и меры защиты
- [`docs/CONFIG.md`](docs/CONFIG.md) — runtime limits и базовые настройки PoC

### Диаграммы и модульные спеки
- [`docs/diagrams/`](docs/diagrams/) — C4 context/container/component, workflow, sequence, state-machine, deployment и data-flow диаграммы
- [`docs/specs/`](docs/specs/) — короткие технические спецификации по orchestrator, tools/retrieval и serving/observability

Эти документы используются как основа для review Milestone 2, планирования реализации и дальнейшего развития системы.

---

## Возможности
- **Агентный triage-цикл**: plan → tool → observe → decide
- **Инструменты (read-only)**: метрики и логи (mock/fixtures; позже — реальные интеграции)
- **База знаний**: поиск runbooks/FAQ (KB или RAG)
- **State & Memory**: история шагов, summary, повторное использование фактов в рамках сессии
- **Safety**: PII redaction, tool allowlist, approval
- **Observability**: structured logs + метрики + трейсинг шагов агента
- **Evals**: набор тест-кейсов и рубрика качества (accuracy/plan-quality/safety)
