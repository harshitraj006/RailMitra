"""Request limit validation and tracking service for passenger journeys."""

from typing import Any, Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import ConflictException, RateLimitException
from app.models import ExchangeRequest, Passenger


async def count_requests_for_journey(db: AsyncSession, requester_id: int) -> int:
    """Count all exchange requests submitted by a passenger on their journey.

    Business Rule R3: Accepted, declined, cancelled, and expired requests all count.
    """
    stmt = (
        select(func.count(ExchangeRequest.id))
        .where(ExchangeRequest.requester_id == requester_id)
    )
    count = await db.scalar(stmt)
    return count or 0


async def check_can_request(db: AsyncSession, requester: Passenger, target_id: int) -> int:
    """Validate that a passenger has remaining request quota and is not repeating a target.

    Raises:
        ConflictException (409): If requesting the same target passenger twice.
        RateLimitException (429): If the 3-request journey limit has been reached.

    Returns:
        The current number of requests already sent before this one.
    """
    # 1. Block repeat request to same target on this journey
    dup_stmt = (
        select(ExchangeRequest)
        .where(
            ExchangeRequest.requester_id == requester.id,
            ExchangeRequest.target_id == target_id,
        )
    )
    dup = await db.scalar(dup_stmt)
    if dup:
        raise ConflictException(
            detail="An exchange request has already been sent to this passenger for this journey.",
            code="DUPLICATE_TARGET",
        )

    # 2. Check 3-request journey cap
    used = await count_requests_for_journey(db, requester.id)
    if used >= settings.REQUEST_LIMIT:
        raise RateLimitException(
            detail=f"Request limit reached. Maximum {settings.REQUEST_LIMIT} requests allowed per journey (all statuses count).",
            code="REQUEST_LIMIT_REACHED",
        )

    return used


async def check_group_member_limits(
    db: AsyncSession,
    swaps: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Validate request limits per individual group member for group requests (R7).

    Each member has their own independent limit of 3.
    """
    member_counts: Dict[int, int] = {}
    violations = []

    for swap in swaps:
        req_id = swap["requester_passenger_id"]
        target_id = swap["target_passenger_id"]

        if req_id not in member_counts:
            member_counts[req_id] = await count_requests_for_journey(db, req_id)

        # Check existing duplicate
        dup_stmt = select(ExchangeRequest).where(
            ExchangeRequest.requester_id == req_id,
            ExchangeRequest.target_id == target_id,
        )
        if await db.scalar(dup_stmt):
            violations.append({
                "requester_id": req_id,
                "target_id": target_id,
                "reason": "Duplicate target request",
                "code": "DUPLICATE_TARGET",
            })

        # Check member quota
        if member_counts[req_id] >= settings.REQUEST_LIMIT:
            violations.append({
                "requester_id": req_id,
                "reason": f"Member has already exhausted journey limit of {settings.REQUEST_LIMIT}",
                "code": "REQUEST_LIMIT_REACHED",
            })
        else:
            member_counts[req_id] += 1

    return {
        "is_valid": len(violations) == 0,
        "violations": violations,
    }
