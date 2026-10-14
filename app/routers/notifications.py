"""Notification endpoints for passengers."""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.errors import NotFoundException
from app.models import Notification, Passenger
from app.routers.auth import get_current_passenger
from app.schemas import NotificationResponse

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationResponse])
async def list_notifications(
    current_passenger: Passenger = Depends(get_current_passenger),
    db: AsyncSession = Depends(get_db),
):
    """Get all notifications for the current passenger, newest first."""
    stmt = (
        select(Notification)
        .where(Notification.passenger_id == current_passenger.id)
        .order_by(Notification.created_at.desc())
    )
    result = await db.execute(stmt)
    return [NotificationResponse.model_validate(n) for n in result.scalars().all()]


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int,
    current_passenger: Passenger = Depends(get_current_passenger),
    db: AsyncSession = Depends(get_db),
):
    """Mark a single notification as read."""
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.passenger_id == current_passenger.id,
    )
    notif = (await db.execute(stmt)).scalar_one_or_none()
    if not notif:
        raise NotFoundException(
            detail="Notification not found.",
            code="NOTIFICATION_NOT_FOUND",
        )
    notif.read = True
    await db.commit()
    return NotificationResponse.model_validate(notif)


@router.post("/read-all")
async def mark_all_notifications_read(
    current_passenger: Passenger = Depends(get_current_passenger),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read for the current passenger."""
    stmt = (
        update(Notification)
        .where(
            Notification.passenger_id == current_passenger.id,
            Notification.read == False,
        )
        .values(read=True)
    )
    result = await db.execute(stmt)
    await db.commit()
    return {"message": f"Marked {result.rowcount} notifications as read."}
