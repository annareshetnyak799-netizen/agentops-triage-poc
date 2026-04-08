from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from src.config import settings


@dataclass(slots=True)
class BudgetSnapshot:
    tool_calls_used: int
    tool_calls_remaining: int
    elapsed_seconds: float
    time_remaining_seconds: float


class SessionBudget:
    def __init__(
        self,
        max_tool_calls: int | None = None,
        time_budget_s: int | None = None,
    ) -> None:
        self._max_tool_calls = max_tool_calls or settings.max_tool_calls
        self._time_budget_s = time_budget_s or settings.time_budget_s
        self._tool_calls_used = 0
        self._started_at = monotonic()

    def consume_tool_call(self) -> None:
        if self.tool_budget_exhausted:
            msg = "Tool call budget exhausted."
            raise RuntimeError(msg)
        self._tool_calls_used += 1

    @property
    def tool_calls_used(self) -> int:
        return self._tool_calls_used

    @property
    def tool_calls_remaining(self) -> int:
        return max(self._max_tool_calls - self._tool_calls_used, 0)

    @property
    def elapsed_seconds(self) -> float:
        return monotonic() - self._started_at

    @property
    def time_remaining_seconds(self) -> float:
        return max(self._time_budget_s - self.elapsed_seconds, 0.0)

    @property
    def tool_budget_exhausted(self) -> bool:
        return self._tool_calls_used >= self._max_tool_calls

    @property
    def time_budget_exhausted(self) -> bool:
        return self.elapsed_seconds >= self._time_budget_s

    @property
    def exhausted(self) -> bool:
        return self.tool_budget_exhausted or self.time_budget_exhausted

    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(
            tool_calls_used=self.tool_calls_used,
            tool_calls_remaining=self.tool_calls_remaining,
            elapsed_seconds=self.elapsed_seconds,
            time_remaining_seconds=self.time_remaining_seconds,
        )
