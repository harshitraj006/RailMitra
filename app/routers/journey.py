"""Journey validation router against the simulated reservation dataset."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.errors import BadRequestException, NotFoundException
from app.models import Passenger
from app.schemas import GroupMemberSummary, JourneyValidateRequest, JourneyValidationResponse

router = APIRouter(prefix="/api/journey", tags=["Journey Validation"])


@router.post("/validate", response_model=JourneyValidationResponse)
async def validate_journey(
    req: JourneyValidateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Validate passenger PNR against the simulated reservation chart.

    Never claims live Indian Railways access; strictly verifies against simulated records.
    """
    stmt = (
        select(Passenger)
        .options(selectinload(Passenger.train), selectinload(Passenger.group))
        .where(Passenger.pnr == req.pnr.strip().upper())
    )
    result = await db.execute(stmt)
    passenger = result.scalar_one_or_none()

    if not passenger:
        raise NotFoundException(
            detail="Journey not found in simulated reservation chart. Please verify your simulated PNR.",
            code="PNR_NOT_FOUND",
        )

    # Validate optional train_number filter if supplied
    if req.train_number and passenger.train.number != req.train_number.strip():
        raise BadRequestException(
            detail=f"Train number '{req.train_number}' does not match simulated booking (found {passenger.train.number} - {passenger.train.name}).",
            code="TRAIN_MISMATCH",
        )

    # Validate optional date filter if supplied
    if req.date and passenger.journey_date != req.date.strip():
        raise BadRequestException(
            detail=f"Journey date '{req.date}' does not match simulated booking date ({passenger.journey_date}).",
            code="DATE_MISMATCH",
        )

    # Fetch group members if booking is part of a family group
    group_members = []
    if passenger.group_id:
        group_stmt = (
            select(Passenger)
            .where(
                Passenger.group_id == passenger.group_id,
                Passenger.id != passenger.id,
                Passenger.journey_date == passenger.journey_date,
            )
            .order_by(Passenger.coach, Passenger.berth_no)
        )
        group_res = await db.execute(group_stmt)
        other_members = group_res.scalars().all()
        for m in other_members:
            group_members.append(
                GroupMemberSummary(
                    passenger_id=m.id,
                    name=m.name,
                    coach=m.coach,
                    berth_no=m.berth_no,
                    berth_type=m.berth_type,
                    age=m.age,
                    needs_lower_berth=m.needs_lower_berth,
                )
            )

    return JourneyValidationResponse(
        pnr=passenger.pnr,
        passenger_id=passenger.id,
        passenger_name=passenger.name,
        phone_masked=passenger.phone_masked,
        email_masked=passenger.email_masked,
        train_id=passenger.train.id,
        train_number=passenger.train.number,
        train_name=passenger.train.name,
        journey_date=passenger.journey_date,
        coach=passenger.coach,
        berth_no=passenger.berth_no,
        berth_type=passenger.berth_type,
        boarding_station=passenger.boarding_station,
        destination_station=passenger.destination_station,
        route=passenger.train.route_stations,
        group_name=passenger.group.name if passenger.group else None,
        group_members=group_members,
        age=passenger.age,
        needs_lower_berth=passenger.needs_lower_berth,
    )
