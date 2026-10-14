"""Train simulation and seating layout router."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.errors import NotFoundException
from app.models import Train
from app.schemas import AdvanceTrainResponse
from app.services import expiry as expiry_service

router = APIRouter(tags=["Train & Simulation"])


class AdvanceTrainPayload(BaseModel):
    train_id: Optional[str] = None
    train_number: Optional[str] = None
    current_station: Optional[str] = None
    to_station: Optional[str] = None


@router.post("/api/demo/advance_train", response_model=AdvanceTrainResponse)
async def advance_train_endpoint(
    payload: AdvanceTrainPayload,
    db: AsyncSession = Depends(get_db),
):
    """Advance train along its route station by station, triggering expiry for elapsed exchanges."""
    train_ident = payload.train_id or payload.train_number or "T-101"

    # Resolve train by id or number
    stmt = select(Train).where((Train.id == train_ident) | (Train.number == train_ident))
    train = (await db.execute(stmt)).scalar_one_or_none()
    if not train:
        raise NotFoundException(detail=f"Train '{train_ident}' not found.", code="TRAIN_NOT_FOUND")

    dest_station = payload.to_station or payload.current_station
    res = await expiry_service.advance_train(db, train.id, dest_station)
    return AdvanceTrainResponse(**res)


@router.get("/api/train/{number}/seating")
async def get_train_seating(
    number: str,
    db: AsyncSession = Depends(get_db),
):
    """Get current effective seating for a train, overlaying active TTE-approved exchanges."""
    stmt = select(Train).where((Train.id == number) | (Train.number == number))
    train = (await db.execute(stmt)).scalar_one_or_none()
    if not train:
        raise NotFoundException(detail=f"Train '{number}' not found.", code="TRAIN_NOT_FOUND")

    seating = await expiry_service.get_effective_seating(db, train.id)
    return {
        "train_id": train.id,
        "train_number": train.number,
        "train_name": train.name,
        "route": train.route_stations,
        "current_station": expiry_service.get_train_position(train.id) or train.route_stations[0],
        "seating": seating,
    }
