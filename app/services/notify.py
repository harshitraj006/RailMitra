"""Notification service: in-app notifications + simulated SMS/email to console."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, Passenger, utc_now


async def send(
    db: AsyncSession,
    passenger: Passenger,
    message: str,
    kind: str,
) -> Notification:
    """Create an in-app notification and print simulated SMS/email to console."""
    notif = Notification(
        passenger_id=passenger.id,
        message=message,
        kind=kind,
        created_at=utc_now(),
        read=False,
    )
    db.add(notif)
    await db.flush()

    # Simulated SMS/email console output
    print(f"\n{'─'*60}")
    print(f"  📱 SIMULATED NOTIFICATION [{kind}]")
    print(f"  To: {passenger.phone_masked} | {passenger.email_masked}")
    print(f"  {message}")
    print(f"{'─'*60}\n")

    return notif


async def notify_request_received(
    db: AsyncSession,
    target: Passenger,
    requester_first_name: str,
    offered_coach: str,
    offered_berth: int,
    offered_type: str,
) -> Notification:
    msg = (
        f"New seat exchange request from {requester_first_name}! "
        f"They offer Coach {offered_coach}, Berth {offered_berth} ({offered_type}). "
        f"Please review and respond."
    )
    return await send(db, target, msg, "REQUEST_RECEIVED")


async def notify_request_accepted(
    db: AsyncSession,
    requester: Passenger,
    target_first_name: str,
) -> Notification:
    msg = f"{target_first_name} has accepted your seat exchange request. Awaiting TTE review."
    return await send(db, requester, msg, "REQUEST_ACCEPTED")


async def notify_request_declined(
    db: AsyncSession,
    requester: Passenger,
    target_first_name: str,
) -> Notification:
    msg = f"{target_first_name} has declined your seat exchange request."
    return await send(db, requester, msg, "REQUEST_DECLINED")


async def notify_request_cancelled(
    db: AsyncSession,
    target: Passenger,
    requester_first_name: str,
) -> Notification:
    msg = f"{requester_first_name} has cancelled their exchange request to you."
    return await send(db, target, msg, "REQUEST_CANCELLED")


async def notify_tte_decision(
    db: AsyncSession,
    passenger: Passenger,
    decision: str,
    note: Optional[str] = None,
) -> Notification:
    if decision == "TTE_APPROVED":
        msg = "Your seat exchange has been APPROVED by the TTE. Exchange is now active!"
    elif decision == "TTE_REJECTED":
        msg = "Your seat exchange has been REJECTED by the TTE."
        if note:
            msg += f" Note: {note}"
    else:
        msg = "The TTE has requested CLARIFICATION on your exchange."
        if note:
            msg += f" Note: {note}"
    return await send(db, passenger, msg, "TTE_DECISION")


async def notify_expiry(
    db: AsyncSession,
    passenger: Passenger,
    original_coach: str,
    original_berth: int,
) -> Notification:
    msg = (
        f"Your seat exchange has expired. "
        f"Please return to your original berth: Coach {original_coach}, Berth {original_berth}."
    )
    return await send(db, passenger, msg, "EXPIRY_REMINDER")


async def notify_group_update(
    db: AsyncSession,
    passenger: Passenger,
    confirmed: int,
    total: int,
    group_name: str,
) -> Notification:
    msg = f"Group '{group_name}' exchange progress: {confirmed} of {total} confirmed."
    return await send(db, passenger, msg, "GROUP_UPDATE")
