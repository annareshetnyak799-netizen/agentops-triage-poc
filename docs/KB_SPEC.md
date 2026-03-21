# KB_SPEC — Knowledge Base (runbooks) for AgentOps Triage PoC

## 1) Что хранится в KB
- runbooks по сервисам (markdown)
- known issues / postmortems (опционально)

## 2) Формат документа (рекомендуемый)
Каждый runbook имеет:
- заголовок, сервис, tags
- секции: Symptoms, Triage, Mitigation, Escalation, Links

Пример:
- `runbooks/payments/http_5xx.md`
- `runbooks/payments/db_pool.md`

## 3) Retrieval стратегия (PoC)
Baseline:
- поиск по service + ключевым словам из alert/log signatures
- возвращаем `top_k=3..5` snippets с refs
- правило: agent обязан ссылаться на refs (grounding)

Опционально:
- hybrid BM25 + embeddings (если будет время)

## 4) Защита от injection в KB
- KB считается недоверенным источником
- игнорируем “инструкции”, которые требуют нарушить policy (tool allowlist/approval)