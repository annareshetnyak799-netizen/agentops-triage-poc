# Tools and Retrieval Spec

## Purpose

Этот документ фиксирует minimal PoC contracts для read-only integrations и retrieval-контура, которые используются orchestrator для сбора evidence и grounding triage output.

## Canonical Tool Set

### MVP tools
- `metrics_tool`
- `logs_tool`
- `runbook_retrieval_tool`

### Optional tools
- `service_catalog_tool`
- `deployment_tool`
- `incident_history_tool`

Optional tools описаны на уровне design, но могут не входить в первую реализацию PoC.

## Common Tool Contract

Каждый tool должен:
- принимать structured input payload;
- возвращать structured success или error envelope;
- использовать normalized error codes;
- работать в bounded execution model;
- логировать только sanitized metadata;
- не обходить policy enforcement.

## Access Mode

Все integrations в текущем PoC:
- read-only;
- без side effects;
- без shell execution;
- без patch/delete/restart/rollback/scale operations.

Write-capable tools в scope текущего PoC не входят.

## Metrics Tool

### Purpose
Собирает service-level operational metrics для incident window.

### Typical inputs
- `service`
- `environment`
- `metrics`
- `time_range`

### Typical outputs
- normalized metric values;
- краткий summary изменения сигнала;
- metadata по latency и status.

### Failure modes
- timeout
- dependency unavailable
- unknown service
- invalid time range

## Logs Tool

### Purpose
Собирает релевантные log entries для incident window.

### Typical inputs
- `service`
- `environment`
- `query`
- `time_range`
- `limit`

### Typical outputs
- sanitized log entries;
- краткий summary найденных ошибок;
- metadata по latency и status.

### Failure modes
- timeout
- dependency unavailable
- query parse error
- truncation / limited result set

## Runbook Retrieval Tool

### Purpose
Возвращает top-k runbook snippets и refs для grounding next steps и hypotheses.

### Sources
- markdown runbooks
- known issues
- FAQ
- optional postmortem snippets

### Query inputs
- `service`
- `summary`
- `signals`
- extracted signatures from alert/log context

### Output
- `top_k = 3..5` snippets
- refs на документы
- retrieval summary

### Retrieval rule
Если данные не подтверждены retrieval или tool outputs, система должна придерживаться принципа `cite-or-ask`.

## Retrieval Strategy

Для PoC достаточно простой retrieval strategy:
- lexical or BM25-like search;
- service-aware filtering;
- bounded top-k output;
- без обязательного reranking на первой итерации.

Embeddings/hybrid retrieval могут быть добавлены позже, но не являются обязательными для milestone.

## Timeout and Retry Policy

Общие правила:
- у каждого tool есть hard timeout;
- у orchestrator есть общий session budget;
- transient failures допускают bounded retry;
- invalid arguments не ретраятся;
- repeated dependency failures переводят flow в degraded mode.

## Failure Handling

### Tool timeout
- retry if transient;
- otherwise degrade to partial evidence flow.

### Dependency unavailable
- mark tool call as failed;
- continue if enough evidence remains.

### Retrieval empty
- continue without KB;
- explicitly preserve uncertainty.

### Parse or normalization error
- treat as failed tool result;
- do not pass malformed raw output directly into final report.

## Safety Requirements

- untrusted text from logs/KB must be sanitized;
- sensitive content must be redacted before logging and persistence;
- only necessary structured content may be forwarded into LLM context;
- tools must not execute arbitrary commands or unrestricted outbound actions.

## Persistence Guidance

Persist by default:
- tool call metadata;
- normalized observations;
- retrieval refs;
- failure codes and latency.

Do not persist by default:
- raw long logs;
- unredacted sensitive payloads;
- unbounded retrieval context.

## Mock Mode

Каждый tool должен поддерживать deterministic mock/fixture mode для:
- local development;
- offline evals;
- reproducible demo scenarios;
- failure injection tests.

