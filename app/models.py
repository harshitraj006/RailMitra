"""SQLAlchemy 2.x declarative ORM models with strict constraints and indexes."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime has timezone.utc, converting naive datetimes from SQLite."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class BerthType(str, Enum):
    LOWER = "LOWER"
    MIDDLE = "MIDDLE"
    UPPER = "UPPER"
    SIDE_LOWER = "SIDE_LOWER"
    SIDE_UPPER = "SIDE_UPPER"


class RequestStatus(str, Enum):
    PENDING_CONSENT = "PENDING_CONSENT"
    ACCEPTED_BY_PASSENGER = "ACCEPTED_BY_PASSENGER"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    TTE_APPROVED = "TTE_APPROVED"
    TTE_REJECTED = "TTE_REJECTED"
    CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"


class MatchCategory(str, Enum):
    BEST = "BEST"
    POSSIBLE = "POSSIBLE"


class Train(Base):
    """Train information and route sequence."""
    __tablename__ = "trains"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # e.g., "T-101"
    number: Mapped[str] = mapped_column(String(16), index=True)    # e.g., "12951"
    name: Mapped[str] = mapped_column(String(128))                 # e.g., "Demo Express"
    route_stations: Mapped[List[str]] = mapped_column(JSON)        # Ordered list, e.g., ["S1", "S2", "S3", "S4", "S5"]

    passengers: Mapped[List["Passenger"]] = relationship(back_populates="train", cascade="all, delete-orphan")


class Group(Base):
    """Passenger travel group (family or booking party)."""
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), index=True)

    passengers: Mapped[List["Passenger"]] = relationship(back_populates="group")
    group_requests: Mapped[List["GroupRequest"]] = relationship(back_populates="group")


class Passenger(Base):
    """Simulated passenger reservation record."""
    __tablename__ = "passengers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pnr: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    phone_masked: Mapped[str] = mapped_column(String(32))
    email_masked: Mapped[str] = mapped_column(String(128))
    train_id: Mapped[str] = mapped_column(String(32), ForeignKey("trains.id"), index=True)
    journey_date: Mapped[str] = mapped_column(String(16), index=True)  # YYYY-MM-DD
    coach: Mapped[str] = mapped_column(String(8), index=True)
    berth_no: Mapped[int] = mapped_column(Integer)
    berth_type: Mapped[str] = mapped_column(String(16))  # BerthType values
    boarding_station: Mapped[str] = mapped_column(String(16), index=True)
    destination_station: Mapped[str] = mapped_column(String(16), index=True)
    group_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("groups.id"), nullable=True, index=True)
    age: Mapped[int] = mapped_column(Integer)
    needs_lower_berth: Mapped[bool] = mapped_column(Boolean, default=False)

    train: Mapped["Train"] = relationship(back_populates="passengers")
    group: Mapped[Optional["Group"]] = relationship(back_populates="passengers")
    sessions: Mapped[List["Session"]] = relationship(back_populates="passenger", cascade="all, delete-orphan")
    otp_codes: Mapped[List["OTPCode"]] = relationship(back_populates="passenger", cascade="all, delete-orphan")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="passenger", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_passenger_train_date_coach", "train_id", "journey_date", "coach"),
    )


class GroupRequest(Base):
    """Linked exchange requests submitted collectively by a family group."""
    __tablename__ = "group_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id"), index=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("passengers.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    group: Mapped["Group"] = relationship(back_populates="group_requests")
    exchange_requests: Mapped[List["ExchangeRequest"]] = relationship(back_populates="group_request")


class ExchangeRequest(Base):
    """Peer-to-peer seat exchange request."""
    __tablename__ = "exchange_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requester_id: Mapped[int] = mapped_column(Integer, ForeignKey("passengers.id"), index=True)
    target_id: Mapped[int] = mapped_column(Integer, ForeignKey("passengers.id"), index=True)
    group_request_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("group_requests.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default=RequestStatus.PENDING_CONSENT.value, index=True)
    category: Mapped[str] = mapped_column(String(16))  # BEST or POSSIBLE
    start_station: Mapped[str] = mapped_column(String(16))
    expiry_station: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    requester: Mapped["Passenger"] = relationship(foreign_keys=[requester_id])
    target: Mapped["Passenger"] = relationship(foreign_keys=[target_id])
    group_request: Mapped[Optional["GroupRequest"]] = relationship(back_populates="exchange_requests")
    confirmations: Mapped[List["Confirmation"]] = relationship(back_populates="request", cascade="all, delete-orphan")
    tte_reviews: Mapped[List["TTEReview"]] = relationship(back_populates="request", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_exchange_requester_target", "requester_id", "target_id"),
        Index("ix_exchange_status", "status"),
    )


class OTPCode(Base):
    """Simulated OTP code record with attempt tracking and lock window."""
    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    passenger_id: Mapped[int] = mapped_column(Integer, ForeignKey("passengers.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

    passenger: Mapped["Passenger"] = relationship(back_populates="otp_codes")


class Session(Base):
    """Active passenger session token for bearer authentication."""
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    passenger_id: Mapped[int] = mapped_column(Integer, ForeignKey("passengers.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    passenger: Mapped["Passenger"] = relationship(back_populates="sessions")


class Confirmation(Base):
    """Independent passenger consent verification."""
    __tablename__ = "confirmations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey("exchange_requests.id"), index=True)
    passenger_id: Mapped[int] = mapped_column(Integer, ForeignKey("passengers.id"), index=True)
    decision: Mapped[str] = mapped_column(String(16))  # ACCEPTED or DECLINED
    device_session_id: Mapped[str] = mapped_column(String(64))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    request: Mapped["ExchangeRequest"] = relationship(back_populates="confirmations")
    passenger: Mapped["Passenger"] = relationship()


class TTEReview(Base):
    """Train Ticket Examiner (TTE) decision and notes."""
    __tablename__ = "tte_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey("exchange_requests.id"), index=True)
    tte_name: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(32))  # TTE_APPROVED, TTE_REJECTED, CLARIFICATION_REQUESTED
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    request: Mapped["ExchangeRequest"] = relationship(back_populates="tte_reviews")


class Notification(Base):
    """In-app and simulated passenger notifications."""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    passenger_id: Mapped[int] = mapped_column(Integer, ForeignKey("passengers.id"), index=True)
    message: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(32))  # REQUEST_RECEIVED, REQUEST_ACCEPTED, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    read: Mapped[bool] = mapped_column(Boolean, default=False)

    passenger: Mapped["Passenger"] = relationship(back_populates="notifications")


class AuditLog(Base):
    """Immutable audit trail for compliance and TTE verification."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)  # e.g., "ExchangeRequest", "OTP", "GroupRequest"
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)       # e.g., "CREATED", "CONSENT_ACCEPTED", "TTE_APPROVED"
    actor: Mapped[str] = mapped_column(String(64))                     # Passenger PNR or "tte_demo" or "system"
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
