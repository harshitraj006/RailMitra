"""Consent flow router: incoming requests, respond, cancel."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.database import get_db
from app.errors import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.models import Confirmation, ExchangeRequest, Passenger, RequestStatus, utc_now
from app.routers.auth import get_current_passenger
from app.routers.requests import build_request_detail
from app.schemas import ExchangeRequestDetailResponse, RespondExchangeRequest
from app.services import audit
from app.services import notify
from app.services.state import validate_transition
from app.ws.manager import manager

router = APIRouter(prefix="/api/requests", tags=["Consent Flow"])


@router.get("/incoming", response_model=List[ExchangeRequestDetailResponse])
async def list_incoming_requests(
    current_passenger: Passenger = Depends(get_current_passenger),
    db: AsyncSession = Depends(get_db),
):
    """List exchange requests where the current passenger is the target."""
    stmt = (
        select(ExchangeRequest)
        .options(
            joinedload(ExchangeRequest.requester),
            joinedload(ExchangeRequest.target),
            selectinload(ExchangeRequest.confirmations),
        )
        .where(ExchangeRequest.target_id == current_passenger.id)
        .order_by(ExchangeRequest.created_at.desc())
    )
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [build_request_detail(r) for r in records]


@router.post("/{request_id}/respond", response_model=ExchangeRequestDetailResponse)
async def respond_to_request(
    request_id: int,
    body: RespondExchangeRequest,
    current_passenger: Passenger = Depends(get_current_passenger),
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    db: AsyncSession = Depends(get_db),
):
    """Target passenger accepts or declines an exchange request.

    Only the target's own session may respond (403 WRONG_PASSENGER otherwise).
    """
    stmt = (
        select(ExchangeRequest)
        .options(
            selectinload(ExchangeRequest.requester),
            selectinload(ExchangeRequest.target),
            selectinload(ExchangeRequest.confirmations),
        )
        .where(ExchangeRequest.id == request_id)
    )
    req = (await db.execute(stmt)).scalar_one_or_none()
    if not req:
        raise NotFoundException(
            detail=f"Exchange request {request_id} not found.",
            code="REQUEST_NOT_FOUND",
        )

    # Only the target may respond
    if req.target_id != current_passenger.id:
        raise ForbiddenException(
            detail="Only the target passenger may respond to this request.",
            code="WRONG_PASSENGER",
        )

    # Map ACCEPTED/DECLINED to status
    if body.decision == "ACCEPTED":
        new_status = RequestStatus.ACCEPTED_BY_PASSENGER.value
    else:
        new_status = RequestStatus.DECLINED.value

    # Validate state transition
    validate_transition(req.status, new_status)

    # Update status
    req.status = new_status
    req.updated_at = utc_now()

    # Store confirmation with device_session_id
    confirmation = Confirmation(
        request_id=req.id,
        passenger_id=current_passenger.id,
        decision=body.decision,
        device_session_id=x_session_token or f"sess_{current_passenger.id}",
        decided_at=utc_now(),
    )
    db.add(confirmation)

    # Audit
    await audit.log(
        db, "ExchangeRequest", req.id,
        f"CONSENT_{body.decision}", current_passenger.pnr,
        {"decision": body.decision},
    )

    # Notifications
    if body.decision == "ACCEPTED":
        await notify.notify_request_accepted(
            db, req.requester, req.target.name.split()[0],
        )
        await manager.broadcast_event(
            "request_updated",
            {"request_id": req.id, "status": new_status, "decision": body.decision},
            passenger_ids=[req.requester_id, req.target_id],
            include_tte=True,
        )
    else:
        await notify.notify_request_declined(
            db, req.requester, req.target.name.split()[0],
        )
        await manager.broadcast_event(
            "request_updated",
            {"request_id": req.id, "status": new_status, "decision": body.decision},
            passenger_ids=[req.requester_id, req.target_id],
        )

    await db.commit()

    # Reload fresh with updated relationships
    reload_stmt = (
        select(ExchangeRequest)
        .options(
            selectinload(ExchangeRequest.requester),
            selectinload(ExchangeRequest.target),
            selectinload(ExchangeRequest.confirmations),
        )
        .execution_options(populate_existing=True)
        .where(ExchangeRequest.id == request_id)
    )
    reloaded = (await db.execute(reload_stmt)).scalar_one()
    return build_request_detail(reloaded)


@router.post("/{request_id}/cancel", response_model=ExchangeRequestDetailResponse)
async def cancel_request(
    request_id: int,
    current_passenger: Passenger = Depends(get_current_passenger),
    db: AsyncSession = Depends(get_db),
):
    """Requester cancels an exchange request (only while PENDING_CONSENT). Still counts toward limit."""
    stmt = (
        select(ExchangeRequest)
        .options(
            selectinload(ExchangeRequest.requester),
            selectinload(ExchangeRequest.target),
            selectinload(ExchangeRequest.confirmations),
        )
        .where(ExchangeRequest.id == request_id)
    )
    req = (await db.execute(stmt)).scalar_one_or_none()
    if not req:
        raise NotFoundException(
            detail=f"Exchange request {request_id} not found.",
            code="REQUEST_NOT_FOUND",
        )

    # Only the requester may cancel
    if req.requester_id != current_passenger.id:
        raise ForbiddenException(
            detail="Only the requester may cancel this request.",
            code="WRONG_PASSENGER",
        )

    # Validate state transition (only from PENDING_CONSENT)
    validate_transition(req.status, RequestStatus.CANCELLED.value)

    req.status = RequestStatus.CANCELLED.value
    req.updated_at = utc_now()

    await audit.log(
        db, "ExchangeRequest", req.id,
        "CANCELLED", current_passenger.pnr,
        {"previous_status": "PENDING_CONSENT"},
    )

    # Notify target
    await notify.notify_request_cancelled(
        db, req.target, req.requester.name.split()[0],
    )

    await manager.broadcast_event(
        "request_updated",
        {"request_id": req.id, "status": RequestStatus.CANCELLED.value},
        passenger_ids=[req.requester_id, req.target_id],
    )

    await db.commit()
    reloaded = (await db.execute(stmt)).scalar_one()
    return build_request_detail(reloaded)
