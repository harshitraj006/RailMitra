"""Group exchange request router."""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_db
from app.models import Passenger
from app.routers.auth import get_current_passenger
from app.services import groups as group_service

router = APIRouter(prefix="/api/group-requests", tags=["Group Requests"])


class DesiredSeatSwapItem(BaseModel):
    member_id: int
    target_id: int


class CreateGroupRequestPayload(BaseModel):
    desired_seating: List[DesiredSeatSwapItem] = Field(..., min_length=1)


@router.post("", status_code=201)
async def create_group_request_endpoint(
    payload: CreateGroupRequestPayload,
    current_passenger: Passenger = Depends(get_current_passenger),
    db: AsyncSession = Depends(get_db),
):
    """Submit linked exchange requests for a travel group/family.

    Validates that the caller is in a group and each member's quota is checked individually.
    """
    desired_seating = [item.model_dump() for item in payload.desired_seating]
    result = await group_service.create_group_request(
        db=db,
        caller=current_passenger,
        desired_seating=desired_seating,
    )
    return result


@router.get("/{group_request_id}")
async def get_group_request_endpoint(
    group_request_id: int,
    current_passenger: Passenger = Depends(get_current_passenger),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details and live confirmation progress of a group request."""
    return await group_service.get_group_request_detail(db, group_request_id)
