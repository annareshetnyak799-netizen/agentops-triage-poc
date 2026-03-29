# THREAT_MODEL — AgentOps Triage PoC

## 1) Assets

Ключевые активы системы:
- incident payloads
- tool outputs
- KB content
- session state
- traces / logs / metrics
- final reports
- approval decisions

## 2) Trust boundaries

Основные trust boundaries:
- external client -> API layer
- orchestrator -> LLM provider
- orchestrator -> tool integrations
- orchestrator -> KB / retrieval sources
- system -> observability backend
- system -> session persistence layer

Любые данные, пришедшие из logs, KB и user input, считаются потенциально недоверенными.

## 3) Main threats

### 3.1 Prompt injection
Источник:
- logs
- KB
- alert annotations
- user-provided text

Риск:
- модель начнёт следовать вредным инструкциям из данных вместо system policy.

### 3.2 PII / secret leakage
Источник:
- raw logs
- alert payloads
- copied tokens / identifiers
- traces or debug logs

Риск:
- утечка чувствительных данных в ответы, structured logs или persisted state.

### 3.3 Unsafe action suggestion
Источник:
- hallucinated remediation
- malicious injected text
- overconfident recommendation

Риск:
- система предложит risky action без корректного approval semantics.

### 3.4 Hallucinated unsupported claims
Источник:
- insufficient evidence
- conflicting signals
- degraded dependency state

Риск:
- final report будет звучать уверенно, но не будет опираться на refs/evidence.

### 3.5 Dependency outage / stuck execution
Источник:
- LLM provider failure
- metrics/logs backend failure
- retrieval outage

Риск:
- hanging sessions, misleading empty outputs или некорректный failure handling.

## 4) Mitigations

### 4.1 Input handling
- sanitize untrusted text before use;
- limit length of logs and retrieved snippets;
- do not treat retrieved text as executable instruction.

### 4.2 Grounding policy
- use `cite-or-ask` rule;
- require refs where possible;
- preserve unknowns when evidence is insufficient.

### 4.3 Data protection
- redact PII before logging and before response generation;
- do not persist raw secrets;
- store refs and sanitized summaries instead of full raw outputs where possible.

### 4.4 Action safety
- read-only tools by default;
- write-capable tools disabled in PoC;
- risky recommendations routed through approval checkpoint.

### 4.5 Runtime safety
- bounded retries;
- bounded timeouts;
- session budget enforcement;
- partial completion preferred over unsupported completion.

## 5) Residual risk

Даже после защит остаются:
- false negatives в PII detection;
- ошибочная интерпретация неоднозначных сигналов;
- снижение качества triage при длительном outage зависимостей;
- неполное покрытие edge cases на ограниченном eval dataset.

## 6) Validation and coverage

Риски должны покрываться eval scenarios:
- injection fixtures
- PII fixtures
- tool outage fixtures
- missing-data / conflicting-signal cases
- policy-violation cases
- degraded-mode / budget-exhaustion cases

## 7) PoC note

Текущий threat model ориентирован на bounded PoC с read-only integrations и mock-friendly execution. Для production evolution потребуются дополнительные controls:
- stronger auth / RBAC
- secret management
- tenant isolation
- retention policy
- deeper audit and compliance controls
