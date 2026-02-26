# Governance — безопасность, риски и политика эксплуатации (PoC)

Цель документа: зафиксировать риск-профиль PoC и минимальные меры управления (детект/защита), чтобы проект соответствовал требованиям по safety, evals и наблюдаемости.

## 1) Risk Register

| Риск | Вероятность | Влияние | Детект | Защита | Остаточный риск |
|---|---:|---:|---|---|---|
| PII утечка (логи/тикеты → ответ/логи системы) | M | H | PII-scan тесты, лог-ревью | PII redaction до логирования и до ответа, запрет raw logging | L |
| Prompt injection из KB/logs (“ignore instructions…”) | M | H | спец-кейсы injection в evals | sanitize inputs, system policy, tool allowlist, “cite or ask” | M→L |
| Опасные действия (rm/delete/rollout) без подтверждения | L–M | H | policy-violation тесты, audit trail tool-calls | allowlist инструментов, write запрещён, approval required | L |
| Галлюцинации (выдуманные факты) | M | M | rubric: groundedness, citation rate | требование ссылок на источники; если нет — ask-for-data | M |
| Недоступность tools (timeout/403/5xx) | M | M | метрики ошибок tool-calls, тесты failover | retry+backoff, fallback KB-only, явное сообщение | L–M |
| Утечка секретов/токенов в логах | L | H | secret scanners (basic), ревью логов | не хранить secrets в PoC; маскирование токенов | L |
| Перегруз/стоимость (слишком много tool-calls/токенов) | M | M | лимиты и метрики usage | rate limit, max tool-calls, token budget | L |

Шкала: L/M/H — low/medium/high.

## 2) Политика логов и персональных данных
### 2.1 Принципы
- **No raw PII in logs**: любые потенциальные PII маскируются ДО записи
- Логи должны быть **структурированными** (JSON) и коррелируемыми по `session_id`
- Сохраняем только минимум данных, нужный для отладки и evals

### 2.2 Что логируем
- `session_id`, timestamps, шаги агента (plan/action/observation)
- факты о tool-calls (название, статус, latency, ошибки)
- ссылки на источники (KB ref IDs), но не сырое содержимое документов целиком

### 2.3 Что НЕ логируем
- сырые логи пользователей/тикетов без редактирования
- секреты, токены, пароли
- “полный промпт” без необходимости (если логируем — то с redaction)

## 3) Защита от injection и unsafe контента
### 3.1 Input sanitization
- Любой текст из logs/KB рассматривается как недоверенный
- Сжимать контекст: выкидывать мусор, ограничивать длину (max chars)

### 3.2 Политика агента (“Cite or ask”)
- Если утверждение не подтверждено tools/KB — агент должен:
  - или запросить уточнение,
  - или сказать “нет данных”
- В ответах всегда предпочитать ссылки/цитирование источников (refs)

### 3.3 Контроль инструментов (Tool Governance)
- **Allowlist по умолчанию**: только read-only
- Любые write/dangerous инструменты:
  - выключены в PoC, или
  - требуют `approval=true` + отдельной валидации

## 4) Approval workflow (Human-in-the-loop)
- Действия уровня риска “write/production-impact” нельзя выполнять автоматически
- Агент может:
  - предложить команду/шаг,
  - пометить как `requires_approval`,
  - дождаться подтверждения от пользователя

## 5) Evals как механизм управления рисками
В evals включаем минимум:
- PII cases → ожидаем 0 утечек
- injection cases → ожидаем 0 нарушений policy
- failover cases → корректная деградация
- rubric на groundedness → снижение галлюцинаций

## 6) Политика доступов (PoC)
- PoC работает на mock данных/fixtures
- Нет production secrets
- При добавлении реальных интеграций: только read-only токены, минимальные права