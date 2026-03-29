# Orchestrator Spec

## Purpose

Orchestrator управляет bounded triage session и отвечает за переходы между lifecycle states, вызов retrieval/tools, сбор evidence и формирование итогового structured report.

## Responsibilities

- принять нормализованный incident input от API layer;
- создать или обновить investigation plan;
- определить, нужен ли retrieval и какие tools вызывать;
- координировать lifecycle state transitions;
- нормализовать observations из tools и retrieval;
- обновлять hypotheses и next steps;
- запускать safety and policy checks перед финализацией;
- завершать session в одном из terminal outcomes.

## Execution Loop

Базовый orchestration loop в PoC:

`plan -> retrieve -> tool -> analyze -> decide`

На практике это означает:
1. построить initial plan;
2. при необходимости извлечь runbooks;
3. при необходимости собрать live evidence через tools;
4. синтезировать observations в hypotheses и next steps;
5. выполнить safety checks;
6. завершить session или перейти в degraded / approval flow.

## Lifecycle States

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

Подробная модель переходов определяется в `docs/STATE_MACHINE.md`.

## Stop Conditions

Session должна останавливаться при наступлении одного из условий:
- `completed`
- `partial_completed`
- `waiting_approval`
- `failed`
- исчерпан session time budget
- превышен допустимый tool-call budget
- дальнейший прогресс невозможен без unsafe behavior

## Retry and Fallback Policy

### Tool failures
- transient tool error -> bounded retry;
- repeated transient failure -> `tool_failed` и degraded path;
- invalid arguments / semantic failure -> no retry.

### Retrieval failures
- retrieval empty -> continue without KB if live evidence is available;
- retrieval unavailable -> continue in degraded mode if safe output is still possible.

### Evidence insufficiency
- conflicting or insufficient evidence -> lower confidence, preserve unknowns, prefer partial result over unsupported claim.

## Approval Semantics

Если next step требует human approval:
- orchestrator не исполняет действие автоматически;
- создаёт `ApprovalRequest`;
- переводит session в `waiting_approval`.

В текущем PoC approval не запускает autonomous write execution, потому что write-capable tools отключены.

## PoC Constraints

- bounded number of iterations;
- bounded number of tool calls;
- bounded session runtime;
- read-only integrations only;
- no autonomous write execution;
- partial completion is preferable to hanging or hallucinated completion.

## Inputs and Outputs

### Inputs
- normalized incident input;
- current session state;
- retrieval results;
- tool results;
- approval decision, если flow дошёл до `waiting_approval`.

### Outputs
- updated lifecycle state;
- updated observations / hypotheses / next steps;
- safety events;
- approval requests;
- final report or partial report.

## Failure Outcomes

Orchestrator может завершить session следующими способами:
- `completed` — safe final report ready;
- `partial_completed` — useful result with explicit gaps;
- `waiting_approval` — gated recommendation detected;
- `failed` — trustworthy result cannot be produced safely.

