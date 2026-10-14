"""State machine for exchange request status transitions.

Defines the allowed transitions table and validates all status changes.
"""

from app.errors import ConflictException
from app.models import RequestStatus

# Allowed transitions: from_status -> set of allowed to_statuses
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    RequestStatus.PENDING_CONSENT.value: {
        RequestStatus.ACCEPTED_BY_PASSENGER.value,
        RequestStatus.DECLINED.value,
        RequestStatus.CANCELLED.value,
        RequestStatus.EXPIRED.value,
    },
    RequestStatus.ACCEPTED_BY_PASSENGER.value: {
        RequestStatus.TTE_APPROVED.value,
        RequestStatus.TTE_REJECTED.value,
        RequestStatus.CLARIFICATION_REQUESTED.value,
        RequestStatus.EXPIRED.value,
    },
    RequestStatus.CLARIFICATION_REQUESTED.value: {
        RequestStatus.TTE_APPROVED.value,
        RequestStatus.TTE_REJECTED.value,
        RequestStatus.CLARIFICATION_REQUESTED.value,
        RequestStatus.EXPIRED.value,
    },
    RequestStatus.TTE_APPROVED.value: {
        RequestStatus.EXPIRED.value,
    },
    # Terminal states – no transitions out
    RequestStatus.DECLINED.value: set(),
    RequestStatus.CANCELLED.value: set(),
    RequestStatus.EXPIRED.value: set(),
    RequestStatus.TTE_REJECTED.value: set(),
}


def validate_transition(current_status: str, new_status: str) -> None:
    """Validate a status transition; raise ConflictException (409) if illegal."""
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise ConflictException(
            detail=f"Invalid state transition: {current_status} → {new_status}",
            code="INVALID_STATE_TRANSITION",
        )
