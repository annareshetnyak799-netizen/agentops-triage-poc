# Product Proposal — AgentOps Triage PoC

## 1) Идея и прикладная задача
В on-call режиме инженер тратит время на первичный triage инцидента: собрать симптомы (alerts/metrics/logs), найти релевантный runbook, сформировать гипотезы и первые действия. Это повторяющаяся задача с высокой ценой ошибки: неверные действия могут усугубить сбой (secondary incident), а данные наблюдаемости могут содержать PII/токены.

**Идея:** агентная система, которая по инциденту автоматически:
- собирает контекст через инструменты (read-only: метрики/логи),
- извлекает знания из базы runbooks/FAQ,
- ведёт state & memory сессии,
- формирует структурированный план triage (hypotheses + next steps),
- соблюдает safety: PII redaction, tool allowlist, approval на рискованные действия,
- наблюдаема (logs/metrics/traces) и оценивается через eval harness.

## 2) Для кого и какая боль
**Пользователи**
- SRE/DevOps on-call: быстрее понять “что происходит” и что делать первым
- Platform/Team Lead: меньше эскалаций, единый процесс triage и формат отчёта
- Бизнес: меньше downtime и быстрее восстановление

**Боль сейчас**
- контекст размазан по источникам (алерты, дашборды, логи, runbooks),
- runbooks сложно быстро найти и применить под конкретный сигнал,
- стохастичность ручных решений и человеческий фактор в стрессовой ситуации,
- высокий риск unsafe действий и утечек при копировании логов/токенов.

## 3) Цель и метрики успеха
### Продуктовые (эффективность)
- **TTFA p95 ≤ 30s** — время до первого структурированного плана triage от агента
- **Сокращение triage-time (proxy):** сравнение “человек vs агент” на 10 кейсах

### Агентские (качество)
- **Plan Quality Score (rubric avg):** ≥ 70% кейсов проходят порог “полезный план”
- **Precision@3 next steps ≥ 0.7**
- **Groundedness:** наличие refs (tools/KB) или корректный запрос данных в условиях неопределённости

### Технические (надёжность)
- **Tool success rate ≥ 0.9**
- **Fallback correctness rate ≥ 0.8** (корректная деградация при сбоях tools)

### Safety (must-have)
- **PII leakage rate = 0**
- **Policy violation rate = 0** (нет опасных действий без approval)

## 4) Что именно сделает PoC на демо
На демо показываем 3–4 сценария:
1) Нормальный инцидент: алерт → tools (metrics/logs) → KB (runbooks) → план triage + refs
2) Tools недоступны: retry → fallback KB-only + запрос уточнений
3) Safety кейс: PII/injection в данных → redaction + соблюдение policy
4) Неопределённость: конфликт сигналов → 2–3 гипотезы + уточняющие вопросы (без галлюцинаций)

На каждом сценарии показываем trace шагов агента (`plan → tool → observe → decide`) и аудит tool-calls.

## 5) Что НЕ делает PoC (out-of-scope)
- Нет auto-remediation в проде без человека (no auto-write)
- Нет production-секретов и “реальных” доступов: на PoC используются fixtures/mocks
- Не гарантируем 100% RCA: выдаём гипотезы и первые шаги
- Полноценный UI не обязателен: достаточно CLI/минимального API

## 6) Сценарии использования + edge-cases (расширенно)
### Основные сценарии
- **Spike 5xx:** определить scope (эндпойнт/инстансы), проверить ошибки, зависимость, деплой
- **Latency spike:** проверить saturation (CPU/mem/DB pool), ошибки таймаутов, очереди
- **Queue backlog:** проверить consumer lag/throughput, ошибки обработчиков, DLQ

### Edge-cases
- tools timeout/5xx/403 → retry/backoff → fallback KB-only
- конфликт сигналов (алерт горит, метрики “норм”) → ветвление гипотез + запрос уточнений
- шумные/пустые логи → уточняющие вопросы (какой эндпойнт/версия/окно времени)
- prompt injection в KB/logs → игнорировать, следовать governance policy
- PII/токены в логах → редактирование до ответа и логирования
- агент “не нашёл причину” → честно фиксирует неопределённость, предлагает safe next steps

## 7) Ограничения (SLO и операционные)
### 7.1 SLO / performance
- **p95 end-to-end latency ≤ 30s** (в условиях PoC)
- ограничение `max_tool_calls ≤ 6` на один incident
- `tool_timeout ≤ 3s`, retries только на transient ошибки
- ограничение размера контекста (truncate/summarize)

### 7.2 Бюджет / стоимость (PoC)
- лимит токенов на запрос: например **≤ 4k tokens** (конфиг)
- допустимая стоимость: например **≤ $0.01–$0.03 / incident** (зависит от модели; фиксируем верхнюю границу в конфиге)
- лимиты API-интеграций: rate limit на tool-calls (чтобы не “DDOS-ить” observability)

## 8) Архитектурный набросок
**Компоненты**
- API/CLI вход: `/incident` → новая сессия
- Orchestrator: planner/router + tool executor + state manager
- Tools (read-only):
  - MetricsTool
  - LogsTool
  - KBTool (search runbooks / RAG)
- State & Memory:
  - session store, step history, summaries
- Safety Layer:
  - PII redaction
  - tool policy allowlist
  - approval workflow
- Observability:
  - structured logs + metrics + trace шагов
- Eval Harness:
  - fixtures, rubric, отчет

## 9) Data Flow (как данные идут по системе)
```mermaid
sequenceDiagram
  participant U as User/On-call
  participant API as API/CLI
  participant A as Orchestrator (Agent)
  participant K as KBTool
  participant M as MetricsTool
  participant L as LogsTool
  participant S as Safety Layer
  participant O as Observability

  U->>API: incident payload
  API->>A: start session (session_id)
  A->>K: retrieve runbooks (query)
  A->>M: query metrics (read-only)
  A->>L: query logs (read-only)
  A->>A: observe + update plan
  A->>S: policy check + PII redaction
  S->>O: safe structured logs/metrics (no PII)
  A->>API: report (hypotheses, next steps, refs)
  API->>U: response