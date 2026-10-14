"""Seat exchange request lifecycle router (Creation, Remaining Limits, Mine)."""

from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.errors import BadRequestException
from app.models import ExchangeRequest, MatchCategory, Passenger, RequestStatus
from app.routers.auth import get_current_passenger
from app.schemas import (
    CreateExchangeRequest,
    ExchangeRequestDetailResponse,
    RemainingRequestsResponse,
)
from app.services import audit
from app.services import limits as limits_service
from app.services import matching as matching_service

router = APIRouter(prefix="/api/requests", tags=["Exchange Requests"])


def build_request_detail(req: ExchangeRequest) -> ExchangeRequestDetailResponse:
    """Helper to convert ExchangeRequest ORM model to detailed response schema."""
    req_confirmed = any(
        c.passenger_id == req.requester_id and c.decision == "ACCEPTED"
        for c in req.confirmations
    )
    target_confirmed = any(
        c.passenger_id == req.target_id and c.decision == "ACCEPTED"
        for c in req.confirmations
    )

    return ExchangeRequestDetailResponse(
        id=req.id,
        requester_id=req.requester_id,
        requester_name=req.requester.name,
        requester_coach=req.requester.coach,
        requester_berth_no=req.requester.berth_no,
        requester_berth_type=req.requester.berth_type,
        requester_segment=f"{req.requester.boarding_station} → {req.requester.destination_station}",
        target_id=req.target_id,
        target_name=req.target.name,
        target_coach=req.target.coach,
        target_berth_no=req.target.berth_no,
        target_berth_type=req.target.berth_type,
        target_segment=f"{req.target.boarding_station} → {req.target.destination_station}",
        group_request_id=req.group_request_id,
        status=RequestStatus(req.status),
        category=MatchCategory(req.category),
        start_station=req.start_station,
        expiry_station=req.expiry_station,
        created_at=req.created_at,
        updated_at=req.updated_at,
        requester_confirmed=req_confirmed,
        target_confirmed=target_confirmed,
    )


@router.get("/remaining", response_model=RemainingRequestsResponse)
async def get_remaining_quota(
    current_passenger: Passenger = Depends(get_current_passenger),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve current passenger's remaining exchange request quota (out of 3)."""
    used = await limits_service.count_requests_for_journey(db, current_passenger.id)
    remaining = max(0, settings.REQUEST_LIMIT - used)
    return RemainingRequestsResponse(
        pnr=current_passenger.pnr,
        allowed=settings.REQUEST_LIMIT,
        used=used,
        remaining=remaining,
        max=settings.REQUEST_LIMIT,
    )


@router.post("", response_model=ExchangeRequestDetailResponse, status_code=201)
async def create_exchange_request(
    req: CreateExchangeRequest,
    current_passenger: Passenger = Depends(get_current_passenger),
    db: AsyncSession = Depends(get_db),
):
    """Initiate an exchange request to an eligible co-passenger.

    Re-runs server-side matching to confirm candidate eligibility;
    enforces 3-request journey cap and duplicate target restrictions.
    """
    target_id = req.target_id or req.target_passenger_id
    if not target_id:
        raise BadRequestException(
            detail="target_id is required to create an exchange request.",
            code="TARGET_ID_REQUIRED",
        )

    # 1. Re-run matching server-side (never trust client)
    match_result = await matching_service.find_matches_for_passenger(
        db=db,
        passenger_id=current_passenger.id,
        need=req.need or "sit_together",
    )

    candidate = next(
        (c for c in match_result.candidates if c.candidate_id == target_id),
        None,
    )
    if not candidate:
        raise BadRequestException(
            detail=f"Passenger ID {target_id} is not an eligible exchange candidate.",
            code="INELIGIBLE_TARGET",
        )

    # 2. Check limits & duplicate target rule (R3)
    await limits_service.check_can_request(db, current_passenger, target_id)

    # 3. Create exchange request
    exchange_req = ExchangeRequest(
        requester_id=current_passenger.id,
        target_id=target_id,
        group_request_id=None,
        status=RequestStatus.PENDING_CONSENT.value,
        category=candidate.category,
        start_station=candidate.segment.start,
        expiry_station=candidate.segment.end,
    )
    db.add(exchange_req)
    await db.flush()

    # 4. Audit trail
    await audit.log(
        db=db,
        entity_type="ExchangeRequest",
        entity_id=exchange_req.id,
        action="CREATED",
        actor=current_passenger.pnr,
        details={
            "target_id": target_id,
            "category": candidate.category,
            "segment": f"{candidate.segment.start} → {candidate.segment.end}",
            "proximity_score": candidate.proximity_score,
        },
    )
    await db.commit()

    # Re-query with eager relationships
    stmt = (
        select(ExchangeRequest)
        .options(
            selectinload(ExchangeRequest.requester),
            selectinload(ExchangeRequest.target),
            selectinload(ExchangeRequest.confirmations),
        )
        .where(ExchangeRequest.id == exchange_req.id)
    )
    loaded = (await db.execute(stmt)).scalar_one()

    return build_request_detail(loaded)


@router.get("/mine", response_model=List[ExchangeRequestDetailResponse])
async def list_my_requests(
    current_passenger: Passenger = Depends(get_current_passenger),
    db: AsyncSession = Depends(get_db),
):
    """List all seat exchange requests submitted by the current authenticated passenger."""
    stmt = (
        select(ExchangeRequest)
        .options(
            selectinload(ExchangeRequest.requester),
            selectinload(ExchangeRequest.target),
            selectinload(ExchangeRequest.confirmations),
        )
        .where(ExchangeRequest.requester_id == current_passenger.id)
        .order_by(ExchangeRequest.created_at.desc())
    )
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [build_request_detail(r) for r in records]
