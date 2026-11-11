"""TTE dashboard API router."""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.database import get_db
from app.errors import ConflictException, NotFoundException
from app.models import (
    AuditLog, Confirmation, ExchangeRequest, Passenger,
    RequestStatus, TTEReview, Train, utc_now,
)
from app.routers.auth import require_tte
from app.schemas import (
    AuditLogResponse,
    ExchangeRequestDetailResponse,
    TTERequestViewResponse,
    TTEReviewRequest,
    TTEReviewResponse,
)
from app.services import audit
from app.services import notify
from app.services.state import validate_transition
from app.ws.manager import manager

router = APIRouter(prefix="/api/tte", tags=["TTE Dashboard"])


@router.get("/requests", response_model=List[TTERequestViewResponse])
async def tte_list_requests(
    _tte_actor: str = Depends(require_tte),
    db: AsyncSession = Depends(get_db),
):
    """TTE dashboard: list requests that have target consent (visible after ACCEPTED_BY_PASSENGER)."""
    viewable_statuses = [
        RequestStatus.ACCEPTED_BY_PASSENGER.value,
        RequestStatus.TTE_APPROVED.value,
        RequestStatus.TTE_REJECTED.value,
        RequestStatus.CLARIFICATION_REQUESTED.value,
    ]
    stmt = (
        select(ExchangeRequest)
        .options(
            joinedload(ExchangeRequest.requester).joinedload(Passenger.group),
            joinedload(ExchangeRequest.target).joinedload(Passenger.group),
            selectinload(ExchangeRequest.confirmations),
        )
        .where(ExchangeRequest.status.in_(viewable_statuses))
        .order_by(ExchangeRequest.created_at.desc())
    )
    reqs = (await db.execute(stmt)).scalars().all()

    result = []
    for r in reqs:
        req_consent = any(
            c.passenger_id == r.requester_id and c.decision == "ACCEPTED"
            for c in r.confirmations
        )
        tgt_consent = any(
            c.passenger_id == r.target_id and c.decision == "ACCEPTED"
            for c in r.confirmations
        )
        group_name = None
        if r.requester.group:
            group_name = r.requester.group.name

        result.append(TTERequestViewResponse(
            request_id=r.id,
            train_id=r.requester.train_id,
            status=RequestStatus(r.status),
            start_station=r.start_station,
            expiry_station=r.expiry_station,
            requester_original=f"Coach {r.requester.coach}, Berth {r.requester.berth_no} ({r.requester.berth_type})",
            requester_proposed=f"Coach {r.target.coach}, Berth {r.target.berth_no} ({r.target.berth_type})",
            target_original=f"Coach {r.target.coach}, Berth {r.target.berth_no} ({r.target.berth_type})",
            target_proposed=f"Coach {r.requester.coach}, Berth {r.requester.berth_no} ({r.requester.berth_type})",
            requester_consent=req_consent,
            target_consent=tgt_consent,
            group_name=group_name,
            created_at=r.created_at,
        ))

    return result


@router.post("/requests/{request_id}/review", response_model=TTEReviewResponse)
async def tte_review_request(
    request_id: int,
    body: TTEReviewRequest,
    tte_actor: str = Depends(require_tte),
    db: AsyncSession = Depends(get_db),
):
    """TTE approves, rejects, or requests clarification. Blocked unless both consents exist."""
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

    # Check both consents exist
    has_req_consent = any(
        c.passenger_id == req.requester_id and c.decision == "ACCEPTED"
        for c in req.confirmations
    )
    has_tgt_consent = any(
        c.passenger_id == req.target_id and c.decision == "ACCEPTED"
        for c in req.confirmations
    )

    # The requester's creation IS their consent (implicit). So we consider it always true.
    # But the target MUST have accepted.
    if not has_tgt_consent:
        raise ConflictException(
            detail="Cannot review: target passenger has not yet accepted. Both consents required.",
            code="MISSING_CONSENT",
        )

    # Validate state transition
    validate_transition(req.status, body.decision)

    # Update status
    req.status = body.decision
    req.updated_at = utc_now()

    # Record TTE review
    review = TTEReview(
        request_id=req.id,
        tte_name=tte_actor,
        decision=body.decision,
        note=body.note,
        reviewed_at=utc_now(),
    )
    db.add(review)
    await db.flush()

    # Audit
    await audit.log(
        db, "ExchangeRequest", req.id,
        body.decision, tte_actor,
        {"note": body.note},
    )

    # Notify both passengers
    await notify.notify_tte_decision(db, req.requester, body.decision, body.note)
    await notify.notify_tte_decision(db, req.target, body.decision, body.note)

    await manager.broadcast_event(
        "tte_decision",
        {"request_id": req.id, "decision": body.decision, "note": body.note},
        passenger_ids=[req.requester_id, req.target_id],
        include_tte=True,
    )

    await db.commit()

    return TTEReviewResponse(
        id=review.id,
        request_id=review.request_id,
        tte_name=review.tte_name,
        decision=review.decision,
        note=review.note,
        reviewed_at=review.reviewed_at,
    )


@router.get("/audit", response_model=List[AuditLogResponse])
async def tte_get_audit(
    request_id: int = None,
    _tte_actor: str = Depends(require_tte),
    db: AsyncSession = Depends(get_db),
):
    """TTE can view audit trail, optionally filtered by request_id."""
    stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(200)
    if request_id:
        stmt = stmt.where(
            AuditLog.entity_type == "ExchangeRequest",
            AuditLog.entity_id == request_id,
        )
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return [AuditLogResponse.model_validate(log) for log in logs]


@router.get("/train/{train_id}/summary")
async def tte_train_summary(
    train_id: str,
    _tte_actor: str = Depends(require_tte),
    db: AsyncSession = Depends(get_db),
):
    """TTE dashboard train summary: active exchanges, positions, alerts."""
    from app.services.expiry import get_effective_seating, get_train_position

    train = await db.scalar(select(Train).where(Train.id == train_id))
    if not train:
        raise NotFoundException(detail=f"Train {train_id} not found.", code="TRAIN_NOT_FOUND")

    seating = await get_effective_seating(db, train_id)
    active_count = sum(1 for s in seating if s.get("is_swapped"))
    current_pos = get_train_position(train_id) or "Not started"

    return {
        "train_id": train_id,
        "train_name": train.name,
        "train_number": train.number,
        "route": train.route_stations,
        "current_station": current_pos,
        "total_passengers": len(seating),
        "active_exchanges": active_count,
        "effective_seating": seating,
    }
