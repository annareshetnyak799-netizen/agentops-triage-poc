from src.domain.enums import SessionStatus


ALLOWED_TRANSITIONS: dict[SessionStatus, set[SessionStatus]] = {
    SessionStatus.NEW: {SessionStatus.VALIDATING_INPUT},
    SessionStatus.VALIDATING_INPUT: {
        SessionStatus.PLANNING,
        SessionStatus.FAILED,
    },
    SessionStatus.PLANNING: {
        SessionStatus.RETRIEVING,
        SessionStatus.EXECUTING_TOOLS,
        SessionStatus.ANALYZING,
        SessionStatus.FAILED,
    },
    SessionStatus.RETRIEVING: {
        SessionStatus.EXECUTING_TOOLS,
        SessionStatus.ANALYZING,
        SessionStatus.FAILED,
    },
    SessionStatus.EXECUTING_TOOLS: {
        SessionStatus.ANALYZING,
        SessionStatus.TOOL_FAILED,
        SessionStatus.FAILED,
    },
    SessionStatus.TOOL_FAILED: {
        SessionStatus.ANALYZING,
        SessionStatus.PARTIAL_COMPLETED,
        SessionStatus.FAILED,
    },
    SessionStatus.ANALYZING: {
        SessionStatus.COMPLETED,
        SessionStatus.PARTIAL_COMPLETED,
        SessionStatus.WAITING_APPROVAL,
        SessionStatus.FAILED,
    },
    SessionStatus.WAITING_APPROVAL: {
        SessionStatus.COMPLETED,
        SessionStatus.PARTIAL_COMPLETED,
        SessionStatus.FAILED,
    },
    SessionStatus.PARTIAL_COMPLETED: set(),
    SessionStatus.COMPLETED: set(),
    SessionStatus.FAILED: set(),
}


def can_transition(
    current_status: SessionStatus,
    next_status: SessionStatus,
) -> bool:
    return next_status in ALLOWED_TRANSITIONS.get(current_status, set())


def validate_transition(
    current_status: SessionStatus,
    next_status: SessionStatus,
) -> None:
    if not can_transition(current_status, next_status):
        msg = (
            f"Invalid session transition: "
            f"{current_status.value} -> {next_status.value}"
        )
        raise ValueError(msg)


def is_terminal_status(status: SessionStatus) -> bool:
    return status in {
        SessionStatus.COMPLETED,
        SessionStatus.PARTIAL_COMPLETED,
        SessionStatus.FAILED,
    }
