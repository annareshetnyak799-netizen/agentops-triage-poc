# AgentOps Triage PoC
**Агентная система для триажа инцидентов: собирает сигналы через инструменты (метрики/логи), находит релевантные runbooks в базе знаний, ведёт сессионную память и выдаёт безопасный план действий.**

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](#)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)](#)
[![CI](https://img.shields.io/badge/ci-github_actions-black.svg?logo=githubactions&logoColor=white)](#)
[![Status](https://img.shields.io/badge/status-PoC-orange.svg)](#)

> **Зачем это бизнесу:** меньше простой и дешевле on-call.  
> Система сокращает **время до первого плана действий (TTFA / time-to-first-action)** и помогает снижать **MTTR** за счёт автоматизированного сбора контекста (alerts/metrics/logs), ссылок на источники и **safety-гейта** (PII redaction, tool allowlist, approval).

**Проблема:** в on-call контекст размазан по алертам, дашбордам, логам и runbooks, triage занимает время, а цена ошибки высока (unsafe действия, утечки PII, неверные гипотезы).

---

## Бизнес-ценность и KPI (эффективность)
Система снижает стоимость инцидентов и нагрузку на on-call за счёт ускорения первичного триажа и снижения риска ошибочных действий.

**Кому полезно**
- **SRE/DevOps on-call:** быстрее понять “что происходит и что делать дальше”
- **Платформа/тимлид:** меньше эскалаций и ручной рутины, стандартизированный triage
- **Бизнес:** ниже простой → меньше потерь выручки и репутационных рисков

**Как создаёт ценность**
- сокращает **TTFA** через автоматизированный сбор сигналов (read-only tools) и поиск runbook
- ускоряет **MTTR** через приоритезированные next steps и явные ссылки на источники наблюдений
- снижает риск “сделать хуже” благодаря safety-гейту: маскирование PII, политика инструментов, approval

**Метрики успеха для PoC**
- **p95 time-to-first-action (TTFA) ≤ 30s**
- **≥ 70% кейсов:** план содержит ≥ 3 релевантных next steps (по рубрике evals)
- **Tool success rate ≥ 90%**
- **0 утечек PII** в ответах и логах на тестах
- **0 нарушений политики инструментов** (опасные действия без approval)
- **≤ 10% ошибок tool-call** (retry + fallback)

---

## Что покажем на демо (PoC)
На демо будет 2–3 сценария (с трассировкой шагов агента `plan → tool → observe → decide`):
1) **Нормальный инцидент:** алерт → agent вызывает tools (metrics/logs) → находит runbook → выдаёт план (hypotheses + next steps) со ссылками на источники.
2) **Tools недоступны (timeout/403):** agent делает retry/fallback → деградирует в KB-only режим и запрашивает недостающие данные.
3) **Safety кейс (PII/injection):** данные маскируются, попытки unsafe действий блокируются (approval required).

---

## Что НЕ делает PoC (out-of-scope)
- Не выполняет remediation/изменяющие действия в production автоматически (no auto-write).
- Не работает с production-секретами и реальными доступами (на PoC используются fixtures/mocks).
- Не гарантирует 100% точность RCA: выдаёт гипотезы и первые шаги triage.
- Не предоставляет полноценный UI: достаточно CLI или минимального HTTP API.

---

## Документы
- [`docs/PRODUCT-PROPOSAL.md`](docs/PRODUCT-PROPOSAL.md) — идея, метрики, сценарии, ограничения, архитектура, data flow
- [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md) — risk register, политика логов/PII, защита от injection, approval workflow
- [`docs/METRICS.md`](docs/METRICS.md) — метрики качества PoC (v0)

---

## Возможности
- **Агентный triage-цикл**: plan → tool → observe → decide
- **Инструменты (read-only)**: метрики и логи (mock/fixtures; позже — реальные интеграции)
- **База знаний**: поиск runbooks/FAQ (KB или RAG)
- **State & Memory**: история шагов, summary, повторное использование фактов в рамках сессии
- **Safety**
  - маскирование PII до логирования и до ответа
  - политика инструментов (allowlist/denylist)
  - approval для потенциально опасных действий
- **Observability**: structured logs + метрики + трейсинг шагов агента
- **Evals**: набор тест-кейсов и рубрика качества (accuracy/plan-quality/safety)
