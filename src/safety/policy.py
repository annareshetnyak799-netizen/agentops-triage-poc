from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field


class PolicyCheckResult(BaseModel):
    blocked: bool
    requires_approval: bool
    recommended_action: str | None = None
    trigger: str | None = None
    safety_notes: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


RISKY_PATTERNS = (
    ("restart", r"\brestart\b"),
    ("rollback", r"\broll[\s-]?back\b"),
    ("rollback", r"\brolling back\b"),
    ("revert", r"\brevert\b"),
    ("redeploy", r"\bredeploy\b"),
    ("disable_traffic", r"\bdisable traffic\b"),
    ("disable_traffic", r"\bcut traffic\b"),
    ("scale_down", r"\bscale down\b"),
    ("delete", r"\bdelete\b"),
    ("flush", r"\bflush\b"),
    ("drop", r"\bdrop\b"),
    ("kill", r"\bkill\b"),
    ("terminate", r"\bterminate\b"),
    ("patch_production", r"\bpatch production\b"),
)


def find_risky_action(next_steps: list[str]) -> tuple[str | None, str | None]:
    for step in next_steps:
        normalized_step = step.lower().strip()
        for trigger, pattern in RISKY_PATTERNS:
            if re.search(pattern, normalized_step) is not None:
                return step, trigger
    return None, None


def evaluate_next_steps(next_steps: list[str]) -> PolicyCheckResult:
    recommended_action, trigger = find_risky_action(next_steps)
    requires_approval = recommended_action is not None

    notes = ["No write actions were executed."]

    if requires_approval:
        notes.append(
            "One or more recommended steps may modify system state and "
            "require explicit human approval."
        )

    return PolicyCheckResult(
        blocked=False,
        requires_approval=requires_approval,
        recommended_action=recommended_action,
        trigger=trigger,
        safety_notes=notes,
    )
