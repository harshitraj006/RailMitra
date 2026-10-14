"""Group exchange request service."""

from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import BadRequestException, ConflictException, RateLimitException
from app.models import (
    ExchangeRequest, GroupRequest, MatchCategory, Passenger,
    RequestStatus, utc_now,
)
from app.services import audit
from app.services import limits as limits_service
from app.services import matching as matching_service
from app.services import notify
from app.ws.manager import manager


async def create_group_request(
    db: AsyncSession,
    caller: Passenger,
    desired_seating: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Create linked exchange requests for a family group.

    Each member's limit is checked individually. If any would exceed, reject all.
    """
    if not caller.group_id:
        raise BadRequestException(
            detail="You must be part of a group to create group requests.",
            code="NOT_IN_GROUP",
        )

    # Load group members
    group_stmt = (
        select(Passenger)
        .where(Passenger.group_id == caller.group_id)
    )
    group_members = (await db.scalars(group_stmt)).all()
    group_member_ids = {m.id for m in group_members}

    # Validate all members belong to group
    for swap in desired_seating:
        member_id = swap.get("member_id")
        if member_id not in group_member_ids:
            raise BadRequestException(
                detail=f"Passenger {member_id} is not in your group.",
                code="NOT_GROUP_MEMBER",
            )

    # Check each member's limit individually
    violations = []
    for swap in desired_seating:
        member_id = swap["member_id"]
        target_id = swap["target_id"]

        # Check duplicate
        dup_stmt = select(ExchangeRequest).where(
            ExchangeRequest.requester_id == member_id,
            ExchangeRequest.target_id == target_id,
        )
        if await db.scalar(dup_stmt):
            violations.append({
                "member_id": member_id,
                "target_id": target_id,
                "code": "DUPLICATE_TARGET",
                "detail": f"Member {member_id} already has a request to target {target_id}.",
            })
            continue

        used = await limits_service.count_requests_for_journey(db, member_id)
        if used >= 3:
            member = next(m for m in group_members if m.id == member_id)
            violations.append({
                "member_id": member_id,
                "code": "REQUEST_LIMIT_REACHED",
                "detail": f"Member {member.name} has exhausted their journey limit ({used}/3).",
            })

    if violations:
        raise ConflictException(
            detail=f"Group request rejected: {len(violations)} member(s) have issues. " +
                   str(violations),
            code="GROUP_LIMIT_VIOLATION",
        )

    # Validate each swap via matching engine
    group_req = GroupRequest(
        group_id=caller.group_id,
        created_by=caller.id,
        created_at=utc_now(),
    )
    db.add(group_req)
    await db.flush()

    created_requests = []
    for swap in desired_seating:
        member_id = swap["member_id"]
        target_id = swap["target_id"]
        member = next(m for m in group_members if m.id == member_id)

        # Re-run matching to validate eligibility
        match_result = await matching_service.find_matches_for_passenger(
            db=db, passenger_id=member_id,
        )
        candidate = next(
            (c for c in match_result.candidates if c.candidate_id == target_id),
            None,
        )

        if not candidate:
            raise BadRequestException(
                detail=f"Target {target_id} is not eligible for member {member.name}.",
                code="INELIGIBLE_TARGET",
            )

        ex = ExchangeRequest(
            requester_id=member_id,
            target_id=target_id,
            group_request_id=group_req.id,
            status=RequestStatus.PENDING_CONSENT.value,
            category=candidate.category,
            start_station=candidate.segment.start,
            expiry_station=candidate.segment.end,
        )
        db.add(ex)
        await db.flush()

        await audit.log(db, "ExchangeRequest", ex.id, "CREATED", member.pnr,
                        {"group_request_id": group_req.id, "target_id": target_id})

        # Notify target
        target = await db.scalar(select(Passenger).where(Passenger.id == target_id))
        if target:
            await notify.notify_request_received(
                db, target, member.name.split()[0],
                member.coach, member.berth_no, member.berth_type,
            )
            await manager.broadcast_event(
                "request_received",
                {"request_id": ex.id, "requester": member.name.split()[0]},
                passenger_ids=[target_id],
            )

        created_requests.append(ex)

    await audit.log(db, "GroupRequest", group_req.id, "CREATED", caller.pnr,
                    {"swap_count": len(desired_seating)})
    await db.commit()

    return await get_group_request_detail(db, group_req.id)


def compute_group_status(requests: list) -> str:
    """Derive group status from constituent exchange request statuses."""
    statuses = [r.status for r in requests]

    if any(s in (RequestStatus.DECLINED.value, RequestStatus.TTE_REJECTED.value) for s in statuses):
        return "FAILED"

    if all(s in (
        RequestStatus.ACCEPTED_BY_PASSENGER.value,
        RequestStatus.TTE_APPROVED.value,
    ) for s in statuses):
        return "FULLY_CONFIRMED"

    if any(s in (
        RequestStatus.ACCEPTED_BY_PASSENGER.value,
        RequestStatus.TTE_APPROVED.value,
    ) for s in statuses):
        return "PARTIAL"

    return "PENDING"


async def get_group_request_detail(
    db: AsyncSession,
    group_request_id: int,
) -> Dict[str, Any]:
    """Load group request with all linked exchanges and compute status."""
    gr = await db.scalar(
        select(GroupRequest)
        .options(
            selectinload(GroupRequest.group),
            selectinload(GroupRequest.exchange_requests)
            .selectinload(ExchangeRequest.requester),
            selectinload(GroupRequest.exchange_requests)
            .selectinload(ExchangeRequest.target),
            selectinload(GroupRequest.exchange_requests)
            .selectinload(ExchangeRequest.confirmations),
        )
        .where(GroupRequest.id == group_request_id)
    )
    if not gr:
        from app.errors import NotFoundException
        raise NotFoundException(detail="Group request not found.", code="GROUP_REQUEST_NOT_FOUND")

    creator = await db.scalar(select(Passenger).where(Passenger.id == gr.created_by))

    reqs = gr.exchange_requests
    confirmed = sum(
        1 for r in reqs
        if r.status in (RequestStatus.ACCEPTED_BY_PASSENGER.value, RequestStatus.TTE_APPROVED.value)
    )
    status = compute_group_status(reqs)

    # Build missing info for FAILED status
    missing = []
    if status == "FAILED":
        for r in reqs:
            if r.status in (RequestStatus.DECLINED.value, RequestStatus.TTE_REJECTED.value):
                missing.append({
                    "request_id": r.id,
                    "requester": r.requester.name,
                    "target": r.target.name,
                    "status": r.status,
                })

    from app.routers.requests import build_request_detail
    swap_details = [build_request_detail(r) for r in reqs]

    result = {
        "group_request_id": gr.id,
        "group_id": gr.group_id,
        "group_name": gr.group.name if gr.group else "Unknown",
        "created_by_pnr": creator.pnr if creator else "unknown",
        "status": status,
        "total_swaps": len(reqs),
        "confirmed_swaps": confirmed,
        "is_fully_confirmed": status == "FULLY_CONFIRMED",
        "progress": f"{confirmed} of {len(reqs)} confirmed",
        "swaps": [s.model_dump() for s in swap_details],
    }
    if missing:
        result["missing"] = missing
    return result
