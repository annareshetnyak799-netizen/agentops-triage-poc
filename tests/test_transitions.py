import pytest

from src.domain.enums import SessionStatus
from src.orchestrator.transitions import (
    can_transition,
    is_terminal_status,
    validate_transition,
)


def test_can_transition_allows_valid_transition() -> None:
    assert can_transition(SessionStatus.NEW, SessionStatus.VALIDATING_INPUT) is True
    assert can_transition(SessionStatus.ANALYZING, SessionStatus.COMPLETED) is True


def test_can_transition_rejects_invalid_transition() -> None:
    assert can_transition(SessionStatus.NEW, SessionStatus.COMPLETED) is False
    assert can_transition(SessionStatus.FAILED, SessionStatus.PLANNING) is False


def test_validate_transition_raises_for_invalid_transition() -> None:
    with pytest.raises(ValueError, match="Invalid session transition"):
        validate_transition(SessionStatus.NEW, SessionStatus.COMPLETED)


def test_is_terminal_status_detects_terminal_states() -> None:
    assert is_terminal_status(SessionStatus.COMPLETED) is True
    assert is_terminal_status(SessionStatus.PARTIAL_COMPLETED) is True
    assert is_terminal_status(SessionStatus.FAILED) is True
    assert is_terminal_status(SessionStatus.ANALYZING) is False
