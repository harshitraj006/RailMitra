"""Authentication and session management router."""

from typing import Optional
from fastapi import APIRouter, Depends, Header
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.errors import BadRequestException, ForbiddenException, UnauthorizedException
from app.models import Passenger, Session
from app.schemas import (
    OTPSendRequest,
    OTPSendResponse,
    OTPVerifyRequest,
    OTPVerifyResponse,
    PassengerProfileResponse,
)
from app.services import audit
from app.services import otp as otp_service

router = APIRouter(prefix="/api", tags=["Authentication & Identity"])


async def get_current_passenger(
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    db: AsyncSession = Depends(get_db),
) -> Passenger:
    """Dependency verifying X-Session-Token header.

    One token identifies one passenger. Passenger A cannot act as Passenger B.
    """
    if not x_session_token:
        raise UnauthorizedException(
            detail="Missing X-Session-Token header. Please authenticate.",
            code="UNAUTHORIZED",
        )

    stmt = (
        select(Session)
        .options(
            selectinload(Session.passenger).selectinload(Passenger.group),
            selectinload(Session.passenger).selectinload(Passenger.train),
        )
        .where(Session.token == x_session_token.strip())
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session or not session.passenger:
        raise UnauthorizedException(
            detail="Invalid or expired session token.",
            code="INVALID_SESSION",
        )

    return session.passenger


async def require_tte(
    x_tte_key: Optional[str] = Header(None, alias="X-TTE-Key"),
) -> str:
    """Dependency validating Train Ticket Examiner access key."""
    if not x_tte_key or x_tte_key.strip() != settings.TTE_KEY:
        raise ForbiddenException(
            detail="Forbidden: Invalid or missing X-TTE-Key header.",
            code="FORBIDDEN_TTE_ACCESS",
        )
    return "tte_demo"


@router.post("/otp/send", response_model=OTPSendResponse)
async def send_otp_endpoint(
    req: OTPSendRequest,
    db: AsyncSession = Depends(get_db),
):
    """Dispatch simulated OTP to passenger."""
    result = await otp_service.send_otp(db, req.pnr)
    return OTPSendResponse(**result)


@router.post("/otp/verify", response_model=OTPVerifyResponse)
async def verify_otp_endpoint(
    req: OTPVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify OTP code, enforce max 3 attempts / 10-min lockout, and return session token."""
    code = req.code or req.otp
    if not code:
        raise BadRequestException(detail="Verification code is required.", code="CODE_REQUIRED")

    session = await otp_service.verify_otp(db, req.pnr, code)

    # Re-fetch passenger with group relationship
    stmt = (
        select(Passenger)
        .options(selectinload(Passenger.group))
        .where(Passenger.id == session.passenger_id)
    )
    passenger = (await db.execute(stmt)).scalar_one()

    return OTPVerifyResponse(
        session_token=session.token,
        passenger=PassengerProfileResponse(
            id=passenger.id,
            pnr=passenger.pnr,
            name=passenger.name,
            coach=passenger.coach,
            berth_no=passenger.berth_no,
            berth_type=passenger.berth_type,
            boarding_station=passenger.boarding_station,
            destination_station=passenger.destination_station,
            journey_date=passenger.journey_date,
            train_id=passenger.train_id,
            group_id=passenger.group_id,
            group_name=passenger.group.name if passenger.group else None,
            age=passenger.age,
            needs_lower_berth=passenger.needs_lower_berth,
        ),
    )


@router.get("/me", response_model=PassengerProfileResponse)
async def get_me(current_passenger: Passenger = Depends(get_current_passenger)):
    """Return profile and journey details of current authenticated passenger."""
    return PassengerProfileResponse(
        id=current_passenger.id,
        pnr=current_passenger.pnr,
        name=current_passenger.name,
        coach=current_passenger.coach,
        berth_no=current_passenger.berth_no,
        berth_type=current_passenger.berth_type,
        boarding_station=current_passenger.boarding_station,
        destination_station=current_passenger.destination_station,
        journey_date=current_passenger.journey_date,
        train_id=current_passenger.train_id,
        group_id=current_passenger.group_id,
        group_name=current_passenger.group.name if current_passenger.group else None,
        age=current_passenger.age,
        needs_lower_berth=current_passenger.needs_lower_berth,
    )


@router.post("/logout")
async def logout(
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    current_passenger: Passenger = Depends(get_current_passenger),
    db: AsyncSession = Depends(get_db),
):
    """Invalidate current session token."""
    if x_session_token:
        await db.execute(delete(Session).where(Session.token == x_session_token.strip()))
        await audit.log(
            db=db,
            entity_type="Session",
            entity_id=current_passenger.id,
            action="SESSION_LOGOUT",
            actor=current_passenger.pnr,
        )
        await db.commit()
    return {"message": "Logged out successfully"}
