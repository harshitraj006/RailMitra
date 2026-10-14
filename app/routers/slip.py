"""Digital exchange slip and public verification router."""

import hashlib
import json
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.errors import ConflictException, ForbiddenException, NotFoundException
from app.models import ExchangeRequest, Passenger, RequestStatus
from app.routers.auth import get_current_passenger
from app.schemas import ExchangeSlipResponse

router = APIRouter(prefix="/api", tags=["Digital Slip & Verification"])

DISCLAIMER_TEXT = (
    "Prototype using a simulated reservation dataset. "
    "Not the official Indian Railways reservation chart or database. "
    "Official use would require authorization from Indian Railways."
)


def generate_verification_token(request_id: int, train_id: str, pnr: str) -> str:
    """Generate tamper-evident verification token for an exchange slip."""
    raw = f"{request_id}:{train_id}:{pnr}:{settings.SECRET_KEY}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


@router.get("/requests/{request_id}/slip", response_model=ExchangeSlipResponse)
async def get_exchange_slip(
    request_id: int,
    current_passenger: Passenger = Depends(get_current_passenger),
    db: AsyncSession = Depends(get_db),
):
    """Generate official digital exchange slip for an approved exchange.

    Requires request status to be TTE_APPROVED.
    Only the participating requester or target may access the slip.
    """
    stmt = (
        select(ExchangeRequest)
        .options(
            selectinload(ExchangeRequest.requester).selectinload(Passenger.train),
            selectinload(ExchangeRequest.target).selectinload(Passenger.train),
            selectinload(ExchangeRequest.tte_reviews),
        )
        .where(ExchangeRequest.id == request_id)
    )
    req = (await db.execute(stmt)).scalar_one_or_none()
    if not req:
        raise NotFoundException(detail="Exchange request not found.", code="REQUEST_NOT_FOUND")

    if current_passenger.id not in (req.requester_id, req.target_id):
        raise ForbiddenException(detail="You are not a participant in this exchange.", code="FORBIDDEN")

    if req.status != RequestStatus.TTE_APPROVED.value:
        raise ConflictException(
            detail=f"Slip is only available for approved exchanges. Current status: {req.status}",
            code="EXCHANGE_NOT_APPROVED",
        )

    is_requester = (current_passenger.id == req.requester_id)
    passenger = req.requester if is_requester else req.target
    partner = req.target if is_requester else req.requester

    token = generate_verification_token(req.id, passenger.train_id, passenger.pnr)
    tte_review = req.tte_reviews[-1] if req.tte_reviews else None

    # QR payload with verification token and non-sensitive summary
    qr_payload = {
        "token": token,
        "req_id": req.id,
        "train": passenger.train.number if passenger.train else passenger.train_id,
        "coach": partner.coach,
        "berth": partner.berth_no,
        "valid_until": req.expiry_station,
    }

    return ExchangeSlipResponse(
        slip_id=f"RM-SLIP-{req.id}-{passenger.id}",
        request_id=req.id,
        train_number=passenger.train.number if passenger.train else passenger.train_id,
        train_name=passenger.train.name if passenger.train else "Demo Express",
        journey_date=passenger.journey_date,
        passenger_name=passenger.name,
        pnr=passenger.pnr,
        original_berth=f"Coach {passenger.coach}, Berth {passenger.berth_no} ({passenger.berth_type})",
        exchanged_berth=f"Coach {partner.coach}, Berth {partner.berth_no} ({partner.berth_type})",
        berth_type=partner.berth_type,
        effective_segment=f"{req.start_station} → {req.expiry_station}",
        expiry_station=req.expiry_station,
        tte_approval_status="APPROVED",
        tte_name=tte_review.tte_name if tte_review else "TTE Authorized",
        disclaimer=DISCLAIMER_TEXT,
        qr_data=json.dumps(qr_payload),
    )


@router.get("/verify/{token}")
async def verify_slip_token(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Public read-only verification endpoint.

    Exposes no PNR or raw contact details. Includes prototype disclaimer.
    """
    stmt = (
        select(ExchangeRequest)
        .options(
            selectinload(ExchangeRequest.requester).selectinload(Passenger.train),
            selectinload(ExchangeRequest.target).selectinload(Passenger.train),
            selectinload(ExchangeRequest.tte_reviews),
        )
        .where(ExchangeRequest.status == RequestStatus.TTE_APPROVED.value)
    )
    approved_reqs = (await db.scalars(stmt)).all()

    matched_req: Optional[ExchangeRequest] = None
    matched_passenger: Optional[Passenger] = None
    matched_partner: Optional[Passenger] = None

    for req in approved_reqs:
        # Check requester token
        tok_req = generate_verification_token(req.id, req.requester.train_id, req.requester.pnr)
        if tok_req == token:
            matched_req = req
            matched_passenger = req.requester
            matched_partner = req.target
            break
        # Check target token
        tok_tgt = generate_verification_token(req.id, req.target.train_id, req.target.pnr)
        if tok_tgt == token:
            matched_req = req
            matched_passenger = req.target
            matched_partner = req.requester
            break

    if not matched_req or not matched_passenger or not matched_partner:
        raise NotFoundException(
            detail="Verification token is invalid or the exchange is not currently approved.",
            code="INVALID_VERIFICATION_TOKEN",
        )

    tte_review = matched_req.tte_reviews[-1] if matched_req.tte_reviews else None

    # Privacy-conscious response: No full PNR, no phone, no email
    return {
        "valid": True,
        "verification_token": token,
        "exchange_id": matched_req.id,
        "passenger_initial": matched_passenger.name.split()[0],
        "train_number": matched_passenger.train.number if matched_passenger.train else matched_passenger.train_id,
        "train_name": matched_passenger.train.name if matched_passenger.train else "Demo Express",
        "journey_date": matched_passenger.journey_date,
        "approved_berth": f"Coach {matched_partner.coach}, Berth {matched_partner.berth_no} ({matched_partner.berth_type})",
        "original_berth": f"Coach {matched_passenger.coach}, Berth {matched_passenger.berth_no} ({matched_passenger.berth_type})",
        "effective_segment": f"{matched_req.start_station} → {matched_req.expiry_station}",
        "expiry_station": matched_req.expiry_station,
        "status": matched_req.status,
        "verified_by_tte": tte_review.tte_name if tte_review else "TTE Authorized",
        "disclaimer": DISCLAIMER_TEXT,
    }
