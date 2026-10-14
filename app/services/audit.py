"""Audit logging service for compliance and TTE verification."""

from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, utc_now


async def log(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    action: str,
    actor: str,
    details: Optional[Any] = None,
) -> AuditLog:
    """Record an immutable audit log entry and persist to database.

    Args:
        db: Active SQLAlchemy async session.
        entity_type: Type of entity (e.g., 'Passenger', 'OTP', 'ExchangeRequest', 'Session').
        entity_id: ID of entity.
        action: Specific action performed (e.g., 'OTP_SENT', 'OTP_VERIFIED', 'OTP_LOCKED', 'CREATED').
        actor: Actor initiating the change (e.g., passenger PNR, 'tte_demo', 'system').
        details: Optional JSON-serializable dictionary with extra context.

    Returns:
        The created AuditLog instance.
    """
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        details=details,
        timestamp=utc_now(),
    )
    db.add(entry)
    await db.flush()
    return entry
