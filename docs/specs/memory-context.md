# Memory and Context Management Specification

Covers how the triage agent manages session state, builds LLM prompts, and
prevents context bloat. Cross-references `STATE_MEMORY.md` and `SYSTEM-DESIGN.md §9`.

---

## 1. Scope

This spec governs in-session, episodic memory only. There is no cross-session
memory persistence in the PoC. All state lives in the `TriageSession` object
and is discarded when the session ends.

---

## 2. Data Structures

### 2.1 RollingSummary

Maintained in `src/orchestrator/context.py`. Updated before each LLM call.

```
RollingSummary
  what_we_know    : list[str]   # confirmed facts from observations
  what_we_tried   : list[str]   # executed steps + outcomes
  open_questions  : list[str]   # gaps that block a confident conclusion
```

### 2.2 Observation Window

The `build_session_context` function truncates the observation list before
injecting it into the prompt:

| Setting | Env variable | Default | Description |
|---------|-------------|---------|-------------|
| `max_observations_in_context` | `AGENTOPS_MAX_OBSERVATIONS_IN_CONTEXT` | 5 | Maximum number of observations passed to the LLM |
| `max_observation_chars` | `AGENTOPS_MAX_OBSERVATION_CHARS` | 800 | Maximum characters per observation (hard truncation) |

Observations are taken from the **most recent** entries in `session.observations`
(i.e. `session.observations[:max_observations_in_context]`).

---

## 3. Prompt Construction

### 3.1 Section order

1. System preamble (role, safety rules, output schema)
2. Incident context (title, service, severity, environment)
3. Rolling summary (what we know / tried / open questions)
4. Observations (truncated, PII-redacted)
5. Knowledge-base refs
6. Output schema reminder

### 3.2 Safety invariants

- Every observation passes through `redact_text` (PII redaction) and
  `sanitize_untrusted_text` (injection stripping) before entering the prompt.
- Raw log lines and long retrieval chunks are never included verbatim; they
  are summarised by the tool into a short `observation.summary`.

---

## 4. Context Eviction Policy

When the observation list grows beyond `max_observations_in_context`, older
entries are dropped from the prompt window (not from the session record).
The rolling summary absorbs the dropped context so information is not lost.

Trigger conditions for rolling summary update:
- Every 3 completed tool steps.
- Before the final LLM analysis call.
- When the total observation char count would exceed
  `max_observations_in_context × max_observation_chars`.

---

## 5. Session Budget Interaction

The context management layer is budget-aware:

- `SessionBudget.time_remaining_seconds` is checked before each LLM call.
- If `time_remaining_seconds ≤ 0`, the session transitions to
  `partial_completed` without calling the LLM.
- The LLM timeout is capped at `min(llm_timeout_s, time_remaining_seconds)`.

See `src/orchestrator/service.py` and `docs/SYSTEM-DESIGN.md §9` for the
budget enforcement implementation.

---

## 6. Configuration Reference

All settings live in `src/config.py` under the `AGENTOPS_` prefix.

| Setting | Default | Description |
|---------|---------|-------------|
| `AGENTOPS_MAX_OBSERVATIONS_IN_CONTEXT` | `5` | Observation window size |
| `AGENTOPS_MAX_OBSERVATION_CHARS` | `800` | Per-observation char limit |
| `AGENTOPS_MAX_TOOL_CALLS` | `6` | Hard cap on tool calls per session |
| `AGENTOPS_TOOL_TIMEOUT_S` | `3` | Per-tool-call timeout |
| `AGENTOPS_TIME_BUDGET_S` | `30` | Total session wall-clock budget |
| `AGENTOPS_LLM_TIMEOUT_S` | `10` | LLM call timeout (further capped by budget) |
| `AGENTOPS_MAX_RETRIES` | `2` | Retry attempts for retriable tool failures |
