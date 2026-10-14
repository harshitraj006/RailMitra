"""Train simulation and exchange expiry service."""

from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ExchangeRequest, Passenger, RequestStatus, Train, utc_now
from app.services import audit
from app.services import notify
from app.services.state import validate_transition
from app.ws.manager import manager


# In-memory train position tracker: train_id -> current station
_train_positions: Dict[str, str] = {}


def get_train_position(train_id: str) -> Optional[str]:
    return _train_positions.get(train_id)


def set_train_position(train_id: str, station: str) -> None:
    _train_positions[train_id] = station


def reset_train_positions() -> None:
    _train_positions.clear()


async def advance_train(
    db: AsyncSession,
    train_id: str,
    to_station: Optional[str] = None,
) -> Dict[str, Any]:
    """Advance train to next station (or specified station) and expire exchanges."""
    train = await db.scalar(select(Train).where(Train.id == train_id))
    if not train:
        from app.errors import NotFoundException
        raise NotFoundException(detail=f"Train {train_id} not found.", code="TRAIN_NOT_FOUND")

    route = train.route_stations
    route_idx = {s: i for i, s in enumerate(route)}
    current = get_train_position(train_id)

    if to_station:
        if to_station not in route_idx:
            from app.errors import BadRequestException
            raise BadRequestException(
                detail=f"Station '{to_station}' is not on route {route}",
                code="INVALID_STATION",
            )
        new_station = to_station
    else:
        if current is None:
            new_station = route[0]
        else:
            cur_idx = route_idx.get(current, 0)
            if cur_idx + 1 >= len(route):
                new_station = route[-1]
            else:
                new_station = route[cur_idx + 1]

    set_train_position(train_id, new_station)
    new_idx = route_idx[new_station]

    # Find exchanges to expire
    active_statuses = [
        RequestStatus.ACCEPTED_BY_PASSENGER.value,
        RequestStatus.TTE_APPROVED.value,
    ]
    pending_statuses = [RequestStatus.PENDING_CONSENT.value]

    # 1. Expire ACCEPTED/TTE_APPROVED where expiry_station index <= current index
    active_stmt = (
        select(ExchangeRequest)
        .options(
            selectinload(ExchangeRequest.requester),
            selectinload(ExchangeRequest.target),
        )
        .where(ExchangeRequest.status.in_(active_statuses))
    )
    active_reqs = (await db.scalars(active_stmt)).all()

    expired_count = 0
    notif_count = 0

    for req in active_reqs:
        # Check train matches
        if req.requester.train_id != train_id:
            continue
        exp_idx = route_idx.get(req.expiry_station, 999)
        if exp_idx <= new_idx:
            old_status = req.status
            validate_transition(old_status, RequestStatus.EXPIRED.value)
            req.status = RequestStatus.EXPIRED.value
            req.updated_at = utc_now()

            await audit.log(db, "ExchangeRequest", req.id, "EXPIRED", "system",
                            {"reason": f"Train reached {new_station}, expiry was {req.expiry_station}"})

            # Notify both passengers
            await notify.notify_expiry(db, req.requester, req.requester.coach, req.requester.berth_no)
            await notify.notify_expiry(db, req.target, req.target.coach, req.target.berth_no)
            notif_count += 2
            expired_count += 1

            await manager.broadcast_event(
                "exchange_expired",
                {"request_id": req.id, "expiry_station": req.expiry_station,
                 "current_station": new_station},
                passenger_ids=[req.requester_id, req.target_id],
                include_tte=True,
            )

    # 2. Expire PENDING_CONSENT where start_station has been passed
    pending_stmt = (
        select(ExchangeRequest)
        .options(
            selectinload(ExchangeRequest.requester),
            selectinload(ExchangeRequest.target),
        )
        .where(ExchangeRequest.status.in_(pending_statuses))
    )
    pending_reqs = (await db.scalars(pending_stmt)).all()

    for req in pending_reqs:
        if req.requester.train_id != train_id:
            continue
        start_idx = route_idx.get(req.start_station, 0)
        if start_idx < new_idx:
            validate_transition(req.status, RequestStatus.EXPIRED.value)
            req.status = RequestStatus.EXPIRED.value
            req.updated_at = utc_now()
            await audit.log(db, "ExchangeRequest", req.id, "EXPIRED", "system",
                            {"reason": f"Pending request expired: start station {req.start_station} passed"})
            expired_count += 1

    await db.commit()

    return {
        "train_id": train_id,
        "current_station": new_station,
        "expired_requests_count": expired_count,
        "notifications_dispatched": notif_count,
    }


async def get_effective_seating(
    db: AsyncSession,
    train_id: str,
) -> List[Dict[str, Any]]:
    """Return current effective seating: original allocation overlaid with active approved exchanges."""
    passengers_stmt = (
        select(Passenger)
        .where(Passenger.train_id == train_id)
        .order_by(Passenger.coach, Passenger.berth_no)
    )
    passengers = (await db.scalars(passengers_stmt)).all()

    # Find active approved exchanges
    active_stmt = (
        select(ExchangeRequest)
        .where(
            ExchangeRequest.status == RequestStatus.TTE_APPROVED.value,
        )
        .options(
            selectinload(ExchangeRequest.requester),
            selectinload(ExchangeRequest.target),
        )
    )
    active_exchanges = (await db.scalars(active_stmt)).all()

    # Build swap map: passenger_id -> (effective_coach, effective_berth, effective_type, swap_with_name)
    swap_map: Dict[int, Dict[str, Any]] = {}
    for ex in active_exchanges:
        if ex.requester.train_id != train_id:
            continue
        # Requester sits in target's berth; target sits in requester's berth
        swap_map[ex.requester_id] = {
            "effective_coach": ex.target.coach,
            "effective_berth_no": ex.target.berth_no,
            "effective_berth_type": ex.target.berth_type,
            "swap_with": ex.target.name.split()[0],
            "exchange_id": ex.id,
        }
        swap_map[ex.target_id] = {
            "effective_coach": ex.requester.coach,
            "effective_berth_no": ex.requester.berth_no,
            "effective_berth_type": ex.requester.berth_type,
            "swap_with": ex.requester.name.split()[0],
            "exchange_id": ex.id,
        }

    result = []
    for p in passengers:
        entry = {
            "passenger_id": p.id,
            "name": p.name,
            "pnr": p.pnr,
            "original_coach": p.coach,
            "original_berth_no": p.berth_no,
            "original_berth_type": p.berth_type,
            "boarding_station": p.boarding_station,
            "destination_station": p.destination_station,
        }
        swap = swap_map.get(p.id)
        if swap:
            entry["effective_coach"] = swap["effective_coach"]
            entry["effective_berth_no"] = swap["effective_berth_no"]
            entry["effective_berth_type"] = swap["effective_berth_type"]
            entry["is_swapped"] = True
            entry["swap_with"] = swap["swap_with"]
            entry["exchange_id"] = swap["exchange_id"]
        else:
            entry["effective_coach"] = p.coach
            entry["effective_berth_no"] = p.berth_no
            entry["effective_berth_type"] = p.berth_type
            entry["is_swapped"] = False
        result.append(entry)

    return result
