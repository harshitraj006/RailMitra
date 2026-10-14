"""Simulated OTP dispatch, cryptographic verification, lockout, and session creation."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Any, Dict, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.errors import BadRequestException, LockedException, NotFoundException
from app.models import OTPCode, Passenger, Session, ensure_utc, utc_now
from app.services import audit


def hash_otp_with_salt(code: str, salt: str) -> str:
    """Hash simulated OTP with random salt using SHA-256."""
    salted = f"{salt}:{code}".encode("utf-8")
    digest = hashlib.sha256(salted).hexdigest()
    return f"{salt}${digest}"


def verify_otp_hash(code: str, stored_hash: str) -> bool:
    """Verify clear-text OTP against stored salt$digest."""
    try:
        salt, digest = stored_hash.split("$", 1)
        expected = hash_otp_with_salt(code, salt)
        return hmac.compare_digest(expected, stored_hash)
    except Exception:
        return False


async def send_otp(db: AsyncSession, pnr: str) -> Dict[str, Any]:
    """Generate, hash, and dispatch a 6-digit simulated OTP."""
    clean_pnr = pnr.strip().upper()
    passenger = await db.scalar(
        select(Passenger).where(Passenger.pnr == clean_pnr)
    )
    if not passenger:
        raise NotFoundException(
            detail=f"Passenger with PNR '{clean_pnr}' not found in simulated reservation chart.",
            code="PNR_NOT_FOUND",
        )

    now = utc_now()

    # Check if passenger is currently locked out
    lock_stmt = (
        select(OTPCode)
        .where(
            OTPCode.passenger_id == passenger.id,
            OTPCode.locked_until.isnot(None),
        )
        .order_by(OTPCode.id.desc())
        .limit(1)
    )
    locked_record = await db.scalar(lock_stmt)
    if locked_record and locked_record.locked_until:
        locked_until_utc = ensure_utc(locked_record.locked_until)
        if locked_until_utc and locked_until_utc > now:
            rem_seconds = int((locked_until_utc - now).total_seconds())
            if rem_seconds > 0:
                raise LockedException(
                    detail=f"Account is temporarily locked due to repeated failed attempts. Please try again in {rem_seconds} seconds.",
                    code="ACCOUNT_LOCKED",
                )

    # Invalidate previous unverified OTP codes
    await db.execute(
        update(OTPCode)
        .where(OTPCode.passenger_id == passenger.id, OTPCode.verified.is_(False))
        .values(verified=True)
    )

    # Generate 6-digit code
    code = f"{secrets.randbelow(900000) + 100000}"
    salt = secrets.token_hex(8)
    code_hash = hash_otp_with_salt(code, salt)
    expires_at = now + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

    new_otp = OTPCode(
        passenger_id=passenger.id,
        code_hash=code_hash,
        expires_at=expires_at,
        attempts=0,
        locked_until=None,
        verified=False,
    )
    db.add(new_otp)
    await db.flush()

    # Write audit log
    await audit.log(
        db=db,
        entity_type="OTP",
        entity_id=new_otp.id,
        action="OTP_SENT",
        actor=passenger.pnr,
        details={"expires_at": expires_at.isoformat()},
    )
    await db.commit()

    # Simulated notification to console
    if settings.DEMO_MODE:
        print(f"\n{'='*60}")
        print(f" [SIMULATED SMS / EMAIL NOTIFICATION]")
        print(f" To: {passenger.phone_masked} | Email: {passenger.email_masked}")
        print(f" RailMitra OTP verification code: {code}")
        print(f" Valid for {settings.OTP_EXPIRY_MINUTES} minutes.")
        print(f"{'='*60}\n")

    return {
        "success": True,
        "message": f"Verification code sent to {passenger.phone_masked}.",
        "pnr": passenger.pnr,
        "masked_phone": passenger.phone_masked,
        "masked_email": passenger.email_masked,
        "demo_otp": code if settings.DEMO_MODE else None,
        "demo_code": code if settings.DEMO_MODE else None,
        "expires_in_seconds": settings.OTP_EXPIRY_MINUTES * 60,
    }


async def verify_otp(db: AsyncSession, pnr: str, code: str) -> Session:
    """Verify submitted code, handle attempt limits and locking, issue session."""
    clean_pnr = pnr.strip().upper()
    clean_code = code.strip()

    passenger = await db.scalar(
        select(Passenger)
        .options(selectinload(Passenger.group))
        .where(Passenger.pnr == clean_pnr)
    )
    if not passenger:
        raise NotFoundException(
            detail=f"Passenger with PNR '{clean_pnr}' not found.",
            code="PNR_NOT_FOUND",
        )

    now = utc_now()

    # Check lock status
    latest_stmt = (
        select(OTPCode)
        .where(OTPCode.passenger_id == passenger.id)
        .order_by(OTPCode.id.desc())
        .limit(1)
    )
    latest_otp = await db.scalar(latest_stmt)

    if latest_otp and latest_otp.locked_until:
        locked_until_utc = ensure_utc(latest_otp.locked_until)
        if locked_until_utc and locked_until_utc > now:
            rem_seconds = int((locked_until_utc - now).total_seconds())
            raise LockedException(
                detail=f"Account is temporarily locked. Try again in {rem_seconds} seconds.",
                code="ACCOUNT_LOCKED",
            )

    # Check active unverified code
    unverified_stmt = (
        select(OTPCode)
        .where(OTPCode.passenger_id == passenger.id, OTPCode.verified.is_(False))
        .order_by(OTPCode.id.desc())
        .limit(1)
    )
    otp_record = await db.scalar(unverified_stmt)

    if not otp_record:
        raise BadRequestException(
            detail="No active verification code found. Please request a new OTP.",
            code="NO_ACTIVE_OTP",
        )

    # Check expiration
    expires_at_utc = ensure_utc(otp_record.expires_at)
    if expires_at_utc and expires_at_utc < now:
        await audit.log(
            db=db,
            entity_type="OTP",
            entity_id=otp_record.id,
            action="OTP_EXPIRED",
            actor=passenger.pnr,
            details={"expired_at": otp_record.expires_at.isoformat()},
        )
        await db.commit()
        raise BadRequestException(
            detail="Verification code has expired. Please request a new code.",
            code="OTP_EXPIRED",
        )

    # Validate code
    is_valid = verify_otp_hash(clean_code, otp_record.code_hash)
    if not is_valid:
        otp_record.attempts += 1
        if otp_record.attempts >= settings.OTP_MAX_ATTEMPTS:
            locked_until = now + timedelta(minutes=settings.OTP_LOCK_MINUTES)
            otp_record.locked_until = locked_until
            rem_seconds = settings.OTP_LOCK_MINUTES * 60
            await audit.log(
                db=db,
                entity_type="OTP",
                entity_id=otp_record.id,
                action="OTP_LOCKED",
                actor=passenger.pnr,
                details={
                    "attempts": otp_record.attempts,
                    "locked_until": locked_until.isoformat(),
                    "seconds_locked": rem_seconds,
                },
            )
            await db.commit()
            raise LockedException(
                detail=f"Maximum verification attempts exceeded. Account locked for {settings.OTP_LOCK_MINUTES} minutes ({rem_seconds} seconds remaining).",
                code="ACCOUNT_LOCKED",
            )
        else:
            remaining = settings.OTP_MAX_ATTEMPTS - otp_record.attempts
            await audit.log(
                db=db,
                entity_type="OTP",
                entity_id=otp_record.id,
                action="OTP_FAILED",
                actor=passenger.pnr,
                details={"attempts": otp_record.attempts, "remaining": remaining},
            )
            await db.commit()
            raise BadRequestException(
                detail=f"Invalid verification code. {remaining} attempt(s) remaining.",
                code="INVALID_OTP",
            )

    # Code matches
    otp_record.verified = True
    otp_record.attempts = 0
    otp_record.locked_until = None

    token = secrets.token_hex(32)
    session = Session(
        token=token,
        passenger_id=passenger.id,
        created_at=now,
    )
    db.add(session)

    await audit.log(
        db=db,
        entity_type="OTP",
        entity_id=otp_record.id,
        action="OTP_VERIFIED",
        actor=passenger.pnr,
    )
    await audit.log(
        db=db,
        entity_type="Session",
        entity_id=passenger.id,
        action="SESSION_CREATED",
        actor=passenger.pnr,
        details={"token_prefix": token[:8]},
    )
    await db.commit()

    return session
