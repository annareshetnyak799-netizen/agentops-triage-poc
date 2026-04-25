# AgentOps Triage PoC

**Agentic system for incident triage:** automatically gathers signals through tools (metrics/logs), retrieves relevant runbooks from a knowledge base, maintains session memory, and produces a safe, structured action plan.

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](#)
[![Status](https://img.shields.io/badge/status-PoC-orange.svg)](#)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](#docker-compose)

---

## For AI safety researchers

This PoC implements safety patterns relevant to **agentic AI evaluation and control research**, even though the surface domain is incident triage:

- **Bounded agent loop** — explicit `plan → tool → observe → decide` cycle with hard limits on tool calls (`max_tool_calls=6`), per-tool timeout (`tool_timeout=3s`), and total session time budget (`time_budget=30s`). Designed to prevent runaway behavior and keep every agent step individually inspectable.
- **Tool policy and approval gate** — read-only tools by default; write-capable tools disabled in PoC; risky recommendations routed through an explicit approval checkpoint rather than executed silently.
- **PII / secret redaction** — detectors over both agent responses and structured logs; "canary" string fixtures for leak detection; target of 0 leaks on PII test cases.
- **Documented threat model** — assets, trust boundaries, and 5 threat categories (prompt injection, PII/secret leakage, unsafe action suggestion, hallucinated claims, dependency outage), each mapped to mitigations and to required eval fixtures. See [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md).
- **Eval framework with formal rubric** — Plan Quality Rubric (6 criteria, 0–2 each), pass threshold (≥ 8/12 with Safety ≥ 2/2), Precision@3, Tool Success Rate, Fallback Correctness, PII Leakage Rate, Policy Violation Rate. See [`docs/EVALS.md`](docs/EVALS.md).
- **Explainable per-session trace** — every decision (plan, tool call, observation, safety event) is captured in structured logs and OpenTelemetry traces, so agent behavior is auditable post-hoc.
- **Honest residual risk section** — false negatives in PII detection, edge-case coverage gaps, and degraded-mode behavior are explicitly listed, not hidden.

The architectural choice is to treat agent safety as a **layered concern** — bounds (orchestration limits) + policy (tool allowlist + approval) + content filtering (PII redaction) + observability (trace + metrics) + evals (fixtures + rubric) — rather than relying on any single mechanism.

---

## Why this matters

**Business framing:** less downtime, cheaper on-call.
The system reduces **time-to-first-action (TTFA)** and helps lower **MTTR** by automating context collection (alerts/metrics/logs), surfacing source references, and enforcing a **safety gate** (PII redaction, tool allowlist, approval workflow).

**The problem:** during on-call, context is scattered across alerts, dashboards, logs, and runbooks; triage is slow and the cost of mistakes is high (unsafe actions, PII leaks, wrong hypotheses).

---

## Why this is an agentic system (not a chatbot)

In a "plain chat" setup, the engineer decides **what** to query (which metrics/logs), **in what order**, and **how to interpret** the results.
Here, the agent autonomously runs the loop `plan → tool → observe → decide`:

- forms hypotheses and a verification plan,
- selects tools and query parameters,
- interprets results and updates the plan and priorities,
- completes triage with a structured report.

A human is involved only at **approval checkpoints**, when potentially risky actions are proposed.

**On determinism and LLM stochasticity:** we standardize the *process* and *output format* (report structure, policy, approval), and improve reproducibility through configuration (low temperature), tool-call limits, and evals over fixed fixtures.

---

## Business value and KPIs

The system reduces incident cost and on-call load by accelerating initial triage and lowering the risk of erroneous actions.

**Who benefits**

- **SRE / DevOps on-call:** faster understanding of "what's happening and what to do next."
- **Platform / team lead:** fewer escalations and less manual routine; a unified triage process.
- **Business:** faster service recovery and lower losses from degradations.

**Where the impact lands**

- **External (customer-facing) services:** less downtime → lower revenue loss, fewer SLA penalties, less reputational risk.
- **Internal services:** less engineering time lost and fewer process delays (CI/CD, billing, analytics); fewer context switches and escalations.

**Why the safety gate is itself value**

- prevents "secondary incidents": wrong commands or actions in production can make the outage worse;
- reduces the risk of leaks (PII / tokens) into chat or logs;
- enables staged rollout: first recommendations, then read-only diagnostics, then actions only via approval.

---

## Success metrics (PoC)

> Detailed definitions and counting rules: [`docs/METRICS.md`](docs/METRICS.md)

**Definitions (short)**

- **TTFA (time-to-first-action):** time from when the system receives an incident to when the agent emits the **first structured action plan** (hypotheses + top-3 next steps). This measures system-side triage speed and does not depend on human reaction time.
- **MTTR:** time from the onset of service degradation to SLO recovery. In the PoC, MTTR is a **business goal** that we influence by speeding up triage.

**Targets (PoC)**

- **p95 TTFA ≤ 30s**
  *Target applies under PoC conditions: `max_tool_calls ≤ 6`, `tool_timeout ≤ 3s`, read-only tools, bounded context.*
- **Plan Quality Pass Rate ≥ 70%** (rubric pass threshold from `docs/EVALS.md`)
- **Precision@3 next steps ≥ 0.7**
- **Tool success rate ≥ 90%**
- **0 PII leaks** in responses and logs on PII tests
- **0 tool policy violations** (risky actions without approval)
- **≤ 10% tool-call errors** (with retry + fallback)

**How we count (short)**

- `TTFA = t(first_response_with_plan) - t(incident_received)`
- `Tool success rate = successful_calls / total_calls`
- `PII leakage rate`: responses and logs are passed through detectors (regex for email/phone/token + "canary" strings). Target: 0 matches.

---

## What the demo shows (PoC)

The demo includes 3–4 scenarios with full traces of the agent's `plan → tool → observe → decide` steps (no manual tool selection):

1. **Normal incident:** alert → agent calls tools (metrics/logs) → finds runbook → emits plan (hypotheses + next steps) with source references.
2. **Tools unavailable (timeout/403):** agent retries / falls back → degrades to KB-only mode and asks for missing data.
3. **Safety case (PII / injection):** sensitive data is redacted, unsafe actions are blocked (approval required).
4. **Uncertainty:** insufficient or conflicting signals → agent forms 2–3 hypotheses, explicitly flags limitations, and asks clarifying questions instead of guessing.

---

## Out of scope (PoC)

- Does not perform automated remediation or write actions in production (no auto-write).
- Does not work with production secrets or real access (PoC uses fixtures / mocks).
- Does not guarantee 100% RCA accuracy: produces hypotheses and triage first steps.
- Does not provide a full UI: a CLI or minimal HTTP API is sufficient.

---

## Documentation

The project includes product, governance, and implementation-oriented documents that together form the PoC's system design package.

### Main Milestone 2 document

- [`docs/SYSTEM-DESIGN.md`](docs/SYSTEM-DESIGN.md) — consolidated system design: architectural decisions, modules, workflow, state/memory, retrieval, integrations, failure modes, guardrails, and operational limits.

### Product and operational rules

- [`docs/PRODUCT-PROPOSAL.md`](docs/PRODUCT-PROPOSAL.md) — project idea, metrics, scenarios, constraints, architecture, and data flow.
- [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md) — risk register, log and PII policy, prompt injection defenses, approval workflow.
- [`docs/METRICS.md`](docs/METRICS.md) — PoC quality metrics.
- [`docs/EVALS.md`](docs/EVALS.md) — evaluation methodology and report format.

### Implementation documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — overall system architecture and component responsibilities.
- [`docs/API_SPEC.md`](docs/API_SPEC.md) — external API contract.
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — domain entities and relationships.
- [`docs/TOOLS_CONTRACTS.md`](docs/TOOLS_CONTRACTS.md) — tool contracts, interfaces, and safety boundaries.
- [`docs/STATE_MACHINE.md`](docs/STATE_MACHINE.md) — session lifecycle and state transitions.
- [`docs/STATE_MEMORY.md`](docs/STATE_MEMORY.md) — state/memory and summarization policy.
- [`docs/KB_SPEC.md`](docs/KB_SPEC.md) — retrieval pipeline and KB format.
- [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md) — logs, metrics, traces, and degraded-mode observability.
- [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) — assets, trust boundaries, threats, and mitigations.
- [`docs/CONFIG.md`](docs/CONFIG.md) — runtime limits and base PoC configuration.

### Diagrams and module specs

- [`docs/diagrams/`](docs/diagrams) — C4 context/container/component, workflow, sequence, state machine, deployment, and data-flow diagrams.
- [`docs/specs/`](docs/specs) — short technical specifications for the orchestrator, tools/retrieval, and serving/observability layers.

---

## Capabilities

- **Agentic triage loop:** `plan → tool → observe → decide`
- **Tools (read-only):** metrics and logs (mock/fixtures; later — real integrations)
- **Knowledge base:** runbook / FAQ retrieval (KB or RAG)
- **State & memory:** step history, summary, and reuse of facts within a session
- **Safety:** PII redaction, tool allowlist, approval
- **Observability:** structured logs + metrics + per-step agent tracing
- **Evals:** test-case set and quality rubric (accuracy / plan quality / safety)

---

## Requirements

- Python `3.11+`
- [`uv`](https://docs.astral.sh/uv/) for dependency installation and command running

---

## Quick start

### 1. Install dependencies

```
uv sync --extra dev
```

### 2. Prepare environment variables

```
cp .env.example .env
```

By default the project runs in safe local mode:

```
AGENTOPS_LLM_BACKEND=mock
AGENTOPS_REPOSITORY_BACKEND=inmemory
AGENTOPS_WRITE_TOOLS_ENABLED=false
```

For the real OpenAI path, update `.env`:

```
AGENTOPS_LLM_BACKEND=real
AGENTOPS_LLM_PROVIDER=openai
AGENTOPS_LLM_MODEL=gpt-4o-mini
AGENTOPS_LLM_API_KEY=your-api-key
AGENTOPS_LLM_TIMEOUT_S=15
```

For a containerized demo with the real OpenAI path, `AGENTOPS_LLM_TIMEOUT_S=15` is recommended to reduce the risk of premature `partial_completed` due to network latency or slower model responses.

For SQLite persistence:

```
AGENTOPS_REPOSITORY_BACKEND=sqlite
AGENTOPS_SQLITE_URL=sqlite:///./agentops_triage.db
```

### 3. Run the service

```
uv run uvicorn src.api.app:app --reload
```

The service is available at:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/docs`

### 4. Run via Docker Compose

For asynchronous validation and a reproducible demo run, the repository ships a minimal containerization:

```
cp .env.example .env
docker compose up --build
```

In container mode, by default:

- the service listens on `0.0.0.0:8000`;
- backend persistence switches to `sqlite`;
- the SQLite file is stored in the named volume `agentops_triage_data`.

Stop the containers:

```
docker compose down
```

Stop the containers and remove the volume:

```
docker compose down -v
```

---

## Common commands

### Run tests

```
uv run pytest tests
```

### Lint

```
uv run ruff check .
```

### Type check

```
uv run mypy src
```

### Local quality runner

```
uv run python scripts/run_quality_scenarios.py
```

---

## Smoke checks

### Health / readiness / metrics

```
curl -s http://127.0.0.1:8000/health | python -m json.tool
curl -s http://127.0.0.1:8000/ready | python -m json.tool
curl -s http://127.0.0.1:8000/metrics
```

If the service is started via Docker Compose, the same smoke checks apply on `127.0.0.1:8000`.

### Create a triage session

```
curl -s -X POST http://127.0.0.1:8000/incident \
  -H "Content-Type: application/json" \
  -d '{
    "title": "High 5xx rate",
    "service": "payments-api",
    "severity": "P1",
    "timestamp": "2026-04-08T10:00:00Z",
    "summary": "Error rate increased after deploy",
    "signals": ["5xx > 12%", "latency p95 up 3x"],
    "environment": "prod",
    "reporter": "oncall-engineer",
    "alert_payload": {},
    "links": []
  }' | python -m json.tool
```

### Get a session and its trace

```
SESSION_ID="<session-id>"
curl -s "http://127.0.0.1:8000/sessions/$SESSION_ID" | python -m json.tool
curl -s "http://127.0.0.1:8000/sessions/$SESSION_ID/trace" | python -m json.tool
```

### Approval flow

```
SESSION_ID="<session-id>"
APPROVAL_ID="<approval-id>"

curl -s -X POST "http://127.0.0.1:8000/sessions/$SESSION_ID/approval" \
  -H "Content-Type: application/json" \
  -d "{
    \"approval_id\": \"$APPROVAL_ID\",
    \"decision\": \"approved\",
    \"comment\": \"Approved by reviewer.\"
  }" | python -m json.tool
```

---

## Configuration

Full list of runtime parameters (with defaults):

| Variable | Default | Description |
| --- | --- | --- |
| `AGENTOPS_ENVIRONMENT` | `local` | Environment: `local`, `test`, `demo` |
| `AGENTOPS_LOG_LEVEL` | `INFO` | Logging level |
| `AGENTOPS_HOST` | `127.0.0.1` | uvicorn bind address |
| `AGENTOPS_PORT` | `8000` | Port |
| `AGENTOPS_REPOSITORY_BACKEND` | `inmemory` | `inmemory` or `sqlite` |
| `AGENTOPS_SQLITE_URL` | `sqlite:///./agentops_triage.db` | SQLite URL |
| `AGENTOPS_WRITE_TOOLS_ENABLED` | `false` | Allow write-capable tools |
| `AGENTOPS_MAX_TOOL_CALLS` | `6` | Per-session tool-call limit |
| `AGENTOPS_TOOL_TIMEOUT_S` | `3` | Per-tool timeout (seconds) |
| `AGENTOPS_TIME_BUDGET_S` | `30` | Total session time budget (seconds) |
| `AGENTOPS_MAX_RETRIES` | `2` | Retries for transient tool errors |
| `AGENTOPS_LLM_BACKEND` | `mock` | `mock` or `real` |
| `AGENTOPS_LLM_PROVIDER` | `mock` | `mock` or `openai` |
| `AGENTOPS_LLM_MODEL` | `mock-model` | LLM model |
| `AGENTOPS_LLM_TIMEOUT_S` | `10` | LLM call timeout (seconds) |
| `AGENTOPS_LLM_API_KEY` | — | API key (required when `LLM_BACKEND=real`) |
| `AGENTOPS_MAX_OBSERVATIONS_IN_CONTEXT` | `5` | Max observations included in the prompt |
| `AGENTOPS_MAX_OBSERVATION_CHARS` | `800` | Max characters per observation |
| `AGENTOPS_OTEL_ENABLED` | `false` | Enable OpenTelemetry tracing |
| `AGENTOPS_OTEL_SERVICE_NAME` | `agentops-triage-poc` | OTEL service name |
| `AGENTOPS_FORCE_TOOL_FAILURE` | `false` | Forced degraded path (for testing) |

Full example: [`.env.example`](.env.example). Documentation: [`docs/CONFIG.md`](docs/CONFIG.md), [`docs/specs/memory-context.md`](docs/specs/memory-context.md).

---

## Known PoC limitations

- **Synchronous triage:** `POST /incident` runs synchronously — the client holds the HTTP connection until triage completes (up to 30s with `time_budget_s=30`). In production, a background task with polling via `GET /sessions/{id}` is recommended.
- **Mock tools:** metrics, logs, and runbook tools work over fixtures, without real Prometheus / Loki / Confluence integrations.
- **Structured output:** `OpenAIRealLLMAdapter` uses the OpenAI Responses API (`responses.parse`) and requires `openai>=1.51`.
- **Session-scoped memory:** memory is not preserved across sessions (ephemeral). Use `AGENTOPS_REPOSITORY_BACKEND=sqlite` for persistence.
- **Eval vs. prod:** the eval fixture `tools_outage_timeout.json` uses an `AGENTOPS_ENVIRONMENT=test` trigger and does not reproduce the degraded path against a production server.

---

## Research extensions

Natural directions in which this PoC could be extended for AI safety / agent evals research:

- **Dual-judge evaluation** — score the agent's textual output and its action sequence with two separate LLM judges; measure where the two scores diverge as a signal of "says-no-does-yes" behavior in agentic settings.
- **Adversarial eval suite for the safety gate** — systematic prompt-injection fixtures (instruction smuggling via logs / KB / alert annotations), policy-bypass attempts, and PII leak attempts under varied phrasing; measure bypass rate and false-negative rate of the detectors.
- **Inspect AI integration** — port the existing rubric (`docs/EVALS.md`) into an Inspect Scorer and the fixtures into an Inspect Task, so the eval can run alongside other agentic safety evaluations in a standard framework.
- **Capability vs. safety frontier on bounded agents** — vary `max_tool_calls`, `time_budget`, and `max_observations_in_context` and measure how Plan Quality, Tool Success Rate, and Safety Event Rate trade off. A small empirical study of how orchestration bounds shape agent behavior.
- **Faithfulness of the agent's stated reasoning** — compare the agent's stated plan / hypotheses with its actual tool calls and final answer; flag cases where the action sequence does not match the stated intent.

These are concrete starting points for follow-up work, not commitments of the current PoC.

---

## Current status

The PoC currently implements:

- structured HTTP API with a `status / data / meta` envelope
- bounded session-oriented orchestration
- mock and real LLM backends
- approval-gated risky actions
- first-class domain entities for `Incident`, `SessionState`, `InvestigationPlan`, `ToolCall`, `Observation`, `SafetyEvent`
- readiness, health, and Prometheus-style metrics
- explainable per-session trace

The project targets a safe, read-only triage flow and intentionally does not perform automated remediation in production.
