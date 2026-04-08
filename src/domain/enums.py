from enum import StrEnum


class Severity(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class SessionStatus(StrEnum):
    NEW = "new"
    VALIDATING_INPUT = "validating_input"
    PLANNING = "planning"
    RETRIEVING = "retrieving"
    EXECUTING_TOOLS = "executing_tools"
    ANALYZING = "analyzing"
    WAITING_APPROVAL = "waiting_approval"
    TOOL_FAILED = "tool_failed"
    PARTIAL_COMPLETED = "partial_completed"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolCallStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
