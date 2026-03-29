# GOVERNANCE — безопасность, риски и управление (PoC)

Цель: зафиксировать риск-профиль AgentOps Triage PoC и меры управления (детект/защита), чтобы система была безопасной, наблюдаемой и проверяемой через evals.

---

## 1) Risk Register

| Риск | Вероятность | Влияние | Детект | Защита | Остаточный риск (описание) |
|---|---:|---:|---|---|---|
| PII утечка (логи/тикеты → ответ/логи системы) | M | H | PII-evals (fixtures), ревью логов | PII redaction до логирования и до ответа, запрет raw logging | Возможны **false negatives** на нестандартных форматах PII; требуется расширять детекторы и тесты |
| Prompt injection из KB/logs (“ignore instructions…”) | M | H | injection fixtures в evals | sanitize inputs, системная политика, tool allowlist, правило “cite-or-ask” | Агент может выдать “социально-инженерный” текст/совет; уменьшаем через policy+evals, но 100% не гарантируем |
| Опасные действия без подтверждения (delete/rollback/disable) | L–M | H | policy-violation тесты, аудит tool-calls | write отключён по умолчанию, allowlist, `requires_approval=true` | Возможно unsafe **предложение текстом** (без исполнения); контролируем через правила ответа + evals |
| Галлюцинации/выдуманные факты | M | M | rubric groundedness + citation rate | требование refs; если данных нет — ask-for-data; ограничение контекста | Возможны ошибки интерпретации сигналов; снижаем через fixtures+rubric, полностью не убирается |
| Недоступность tools (timeout/403/5xx) | M | M | метрики ошибок tool-calls, failover fixtures | retry+backoff, fallback KB-only, явное сообщение | При длительном outage инструментов падает качество triage; корректная деградация обязательна |
| Утечка секретов/токенов в логах | L | H | secret-pattern scan (basic), ревью | не хранить secrets в PoC; маскирование токенов; запрет raw logging | Нестандартные токены могут пройти; покрываем “canary” строками и расширяем паттерны |
| Перерасход бюджета (токены/tool-calls/latency) | M | M | usage metrics, p95 latency | `max_tool_calls`, token budget, timeouts, truncate/summarize | В тяжёлых кейсах возможны превышения → нужен degrade mode (меньше tool-calls, больше вопросов) |

Шкала: L/M/H — low/medium/high.

---

## 2) Tool Governance и Approval workflow

**Цель:** предотвратить “secondary incidents” и исключить автоматические risky действия.

### 2.1 Allowlist/denylist
- По умолчанию разрешены **только read-only** инструменты: MetricsTool, LogsTool, KBTool.
- В implementation-level контрактах этим logical names соответствуют канонические идентификаторы:
  - `MetricsTool` → `metrics_tool`
  - `LogsTool` → `logs_tool`
  - `KBTool` → `runbook_retrieval_tool`
- Любые write/dangerous действия:
  - выключены в PoC, **или**
  - доступны только через отдельный tool с обязательным `requires_approval=true`.

### 2.2 Approval
- Агент может **предложить** действие (команда/шаг), но обязан:
  - явно пометить его как требующее подтверждения,
  - дождаться подтверждения человека,
  - зафиксировать решение в audit trail.
- В текущем PoC approval используется для gated recommendations и audit trail; write-capable tools по умолчанию отключены.

### 2.3 Audit trail
Каждый tool-call логируется в структурированном виде:
- `session_id`, `tool_name`, `status`, `latency_ms`, `error_type`
- параметры запросов — только в безопасном виде (без PII/секретов)

---

## 3) Политика логов и персональных данных (PII)

### 3.1 Принципы
- **No raw PII in logs:** редактирование до записи в логи и до ответа пользователю
- Логи должны быть **структурированными** (JSON) и коррелируемыми по `session_id`
- Храним минимум данных, необходимых для отладки и evals (data minimization)

### 3.2 Что логируем
- шаги агента: `plan/action/observation/decision`
- tool-calls (см. audit trail)
- ссылки на источники (IDs/refs), но не полный текст документов/логов

### 3.3 Что НЕ логируем
- сырые инцидентные логи без redaction
- токены, пароли, секреты
- полный prompt (если очень нужно — только после redaction и с ограничениями)

---

## 4) Защита от prompt injection и unsafe инструкций

### 4.1 Недоверенные входы
Любой текст из logs/KB рассматривается как **недоверенный**:
- truncate по длине,
- sanitize (удаление мусора/артефактов),
- запрет следования “инструкциям” из данных.

### 4.2 Правило “Cite-or-Ask”
Если утверждение не подтверждено tools/KB:
- агент должен запросить уточнение или сказать “нет данных”,
- предпочтение ответам со ссылками/refs.

---

## 5) Evals как механизм управления рисками (risk → test → metric)

| Риск | Evals сценарий | Метрика/критерий успеха |
|---|---|---|
| PII leakage | PII fixtures (email/phone/token/canary) | `PII leakage rate = 0` в ответах и логах |
| Injection | injected logs/runbooks | `policy violation rate = 0`, игнорирование вредных инструкций |
| Dangerous actions | “предложи delete/rollback/disable” | все risky шаги помечены `requires_approval`, ничего не исполняется |
| Галлюцинации | missing-data / conflicting signals | rubric groundedness ≥ 1, задаёт вопросы вместо догадок |
| Tool outages | timeout/403/5xx fixtures | fallback correctness ≥ 0.8, корректные сообщения об ограничениях |
| Бюджет/latency | heavy-context fixture | p95 latency в ограничениях **или** корректный degrade mode |

---

## 6) Доступы и данные (PoC)

- PoC работает на **fixtures/mocks**, без production secrets.
- При добавлении реальных интеграций:
  - только read-only токены,
  - минимальные права (least privilege),
  - rate limits и лимиты tool-calls.

---

## 7) Mapping на требования Milestone

- **Зона безопасности (PII/опасные действия):** разделы 2–4
- **Risk register:** раздел 1
- **Политика логов и PII:** раздел 3
- **Защиты от injection и подтверждение действий:** разделы 2 и 4
- **Evals/мониторинг/управление рисками:** раздел 5
- **Операционные ограничения и доступы:** раздел 6