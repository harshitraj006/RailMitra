"""Pydantic v2 schemas for all API request and response payloads."""

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models import BerthType, MatchCategory, RequestStatus


# ============================================================================
# Standard Error & Health Schemas
# ============================================================================

class ErrorResponse(BaseModel):
    """Standardized error response shape."""
    detail: str = Field(..., description="Human-readable explanation of error")
    code: str = Field(..., description="Machine-readable error identifier")


class HealthResponse(BaseModel):
    """System health check payload."""
    status: str = "ok"
    app: str = "RailMitra"
    version: str = "0.1.0"
    demo_mode: bool = True
    database_connected: bool = True
    timestamp: datetime


# ============================================================================
# Journey & Identity / OTP Schemas
# ============================================================================

class JourneyValidateRequest(BaseModel):
    """Request payload for validating a passenger PNR."""
    pnr: str = Field(..., description="10-digit simulated passenger name record", min_length=5, max_length=16)


class JourneyValidationResponse(BaseModel):
    """Validation response confirming itinerary from simulated database."""
    pnr: str
    passenger_id: int
    passenger_name: str
    phone_masked: str
    email_masked: str
    train_id: str
    train_number: str
    train_name: str
    journey_date: str
    coach: str
    berth_no: int
    berth_type: str
    boarding_station: str
    destination_station: str
    group_name: Optional[str] = None
    age: int
    needs_lower_berth: bool

    model_config = ConfigDict(from_attributes=True)


class OTPSendRequest(BaseModel):
    """Request to generate and dispatch simulated OTP."""
    pnr: str = Field(..., min_length=5, max_length=16)


class OTPSendResponse(BaseModel):
    """Response returned upon OTP dispatch."""
    success: bool = True
    message: str
    pnr: str
    demo_code: Optional[str] = Field(None, description="Clear-text OTP displayed when DEMO_MODE=True")
    expires_in_seconds: int = 300


class OTPVerifyRequest(BaseModel):
    """Payload to verify OTP and obtain a session token."""
    pnr: str = Field(..., min_length=5, max_length=16)
    otp: str = Field(..., min_length=6, max_length=6)


class PassengerProfileResponse(BaseModel):
    """Passenger summary profile embedded in session verification."""
    id: int
    pnr: str
    name: str
    coach: str
    berth_no: int
    berth_type: str
    boarding_station: str
    destination_station: str
    journey_date: str
    train_id: str
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    age: int
    needs_lower_berth: bool

    model_config = ConfigDict(from_attributes=True)


class OTPVerifyResponse(BaseModel):
    """Authentication success payload with session token."""
    session_token: str
    passenger: PassengerProfileResponse


# ============================================================================
# Matching Engine Schemas
# ============================================================================

class MatchCandidate(BaseModel):
    """A co-passenger candidate evaluated for seat exchange."""
    passenger_id: int
    first_name: str
    coach: str
    berth_no: int
    berth_type: str
    boarding_station: str
    destination_station: str
    category: MatchCategory
    overlap_segment: str
    start_station: str
    expiry_station: str
    why: str
    proximity_score: int
    distance_to_requester: int
    destination_gap: int

    model_config = ConfigDict(from_attributes=True)


class MatchListResponse(BaseModel):
    """List of ranked candidate berths available for exchange."""
    requester_berth: str
    requester_coach: str
    requester_segment: str
    best_matches: List[MatchCandidate]
    possible_matches: List[MatchCandidate]
    total_candidates: int


# ============================================================================
# Exchange Requests Schemas
# ============================================================================

class CreateExchangeRequest(BaseModel):
    """Payload to initiate a peer-to-peer exchange."""
    target_passenger_id: int = Field(..., description="ID of co-passenger to swap with")
    category: MatchCategory
    start_station: str
    expiry_station: str


class ExchangeRequestDetailResponse(BaseModel):
    """Full detail of an exchange request."""
    id: int
    requester_id: int
    requester_name: str
    requester_coach: str
    requester_berth_no: int
    requester_berth_type: str
    requester_segment: str

    target_id: int
    target_name: str
    target_coach: str
    target_berth_no: int
    target_berth_type: str
    target_segment: str

    group_request_id: Optional[int] = None
    status: RequestStatus
    category: MatchCategory
    start_station: str
    expiry_station: str
    created_at: datetime
    updated_at: datetime

    requester_confirmed: bool = False
    target_confirmed: bool = False

    model_config = ConfigDict(from_attributes=True)


class RespondExchangeRequest(BaseModel):
    """Payload for target passenger to accept or decline."""
    decision: str = Field(..., pattern="^(ACCEPTED|DECLINED)$")


class RemainingRequestsResponse(BaseModel):
    """Current journey quota status."""
    pnr: str
    allowed: int = 3
    used: int
    remaining: int


# ============================================================================
# Group Exchange Schemas
# ============================================================================

class SingleGroupMemberSwap(BaseModel):
    """One planned swap within a linked group request."""
    requester_passenger_id: int
    target_passenger_id: int
    category: MatchCategory
    start_station: str
    expiry_station: str


class CreateGroupRequest(BaseModel):
    """Payload to create linked family group requests."""
    swaps: List[SingleGroupMemberSwap]


class GroupRequestDetailResponse(BaseModel):
    """Status of a family group multi-seat exchange."""
    group_request_id: int
    group_id: int
    group_name: str
    created_by_pnr: str
    status: str
    total_swaps: int
    confirmed_swaps: int
    is_fully_confirmed: bool
    swaps: List[ExchangeRequestDetailResponse]


# ============================================================================
# Notification Schemas
# ============================================================================

class NotificationResponse(BaseModel):
    """In-app passenger notification."""
    id: int
    passenger_id: int
    message: str
    kind: str
    created_at: datetime
    read: bool

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# TTE Dashboard & Audit Schemas
# ============================================================================

class TTEReviewRequest(BaseModel):
    """TTE review action."""
    decision: str = Field(..., pattern="^(TTE_APPROVED|TTE_REJECTED|CLARIFICATION_REQUESTED)$")
    note: Optional[str] = None


class TTEReviewResponse(BaseModel):
    """Result of TTE review."""
    id: int
    request_id: int
    tte_name: str
    decision: str
    note: Optional[str]
    reviewed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TTERequestViewResponse(BaseModel):
    """Dashboard record presented to Train Ticket Examiner."""
    request_id: int
    train_id: str
    status: RequestStatus
    start_station: str
    expiry_station: str
    requester_original: str
    requester_proposed: str
    target_original: str
    target_proposed: str
    requester_consent: bool
    target_consent: bool
    group_name: Optional[str]
    created_at: datetime


class AuditLogResponse(BaseModel):
    """Immutable audit trail row."""
    id: int
    entity_type: str
    entity_id: int
    action: str
    actor: str
    details: Optional[Any]
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Digital Exchange Slip Schema
# ============================================================================

class ExchangeSlipResponse(BaseModel):
    """Official digital exchange slip displayed on passenger mobile device."""
    slip_id: str
    request_id: int
    train_number: str
    train_name: str
    journey_date: str
    passenger_name: str
    pnr: str
    original_berth: str
    exchanged_berth: str
    berth_type: str
    effective_segment: str
    expiry_station: str
    tte_approval_status: str
    tte_name: Optional[str]
    disclaimer: str
    qr_data: str


# ============================================================================
# Simulation & Demo Schemas
# ============================================================================

class AdvanceTrainRequest(BaseModel):
    """Advance simulated train station along its route."""
    train_id: str = "T-101"
    to_station: Optional[str] = None


class AdvanceTrainResponse(BaseModel):
    """Result of train movement simulation."""
    train_id: str
    current_station: str
    expired_requests_count: int
    notifications_dispatched: int


class DemoResetResponse(BaseModel):
    """Result of demo database reset."""
    message: str
    passengers_count: int
    trains_count: int
    groups_count: int
