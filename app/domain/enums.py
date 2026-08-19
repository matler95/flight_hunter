from enum import StrEnum


class SearchStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TicketType(StrEnum):
    SINGLE_TICKET = "single_ticket"
    SELF_TRANSFER = "self_transfer"
    UNKNOWN = "unknown"


class VerificationStatus(StrEnum):
    DISCOVERED = "discovered"
    VERIFIED = "verified"
    REJECTED = "rejected"
    UNKNOWN = "unknown"
    ERROR = "error"
