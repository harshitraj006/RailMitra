"""Candidate seat matching router."""

from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Passenger
from app.routers.auth import get_current_passenger
from app.schemas import MatchListResponse
from app.services import matching as matching_service

router = APIRouter(prefix="/api", tags=["Seat Matching Engine"])


@router.get("/match", response_model=MatchListResponse)
async def get_seat_matches(
    need: Optional[str] = "sit_together",
    current_passenger: Passenger = Depends(get_current_passenger),
    db: AsyncSession = Depends(get_db),
):
    """Find and rank candidate co-passengers for peer-to-peer seat exchange.

    Strictly satisfies Business Rule R4:
    - Pure matching logic evaluated server-side
    - Protected berth rule for age 60+ / needs_lower_berth
    - Never exposes candidate PNR, phone, or email
    """
    return await matching_service.find_matches_for_passenger(
        db=db,
        passenger_id=current_passenger.id,
        need=need or "sit_together",
    )
