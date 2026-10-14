"""Matching engine service for peer-to-peer seat exchanges.

Consists of:
1. Pure matching functions without database dependencies (easily unit-tested).
2. A thin SQLAlchemy async database adapter.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ExchangeRequest, MatchCategory, Passenger, RequestStatus, Train
from app.schemas import JourneySegment, MatchCandidate, MatchListResponse


# Lower berths suitable for seniors / mobility requirements
SENIOR_SAFE_BERTHS = {"LOWER", "SIDE_LOWER"}
UPPER_CLIMBING_BERTHS = {"UPPER", "MIDDLE", "SIDE_UPPER"}


@dataclass
class MatchPassenger:
    """Plain data representation of a passenger for pure matching logic."""
    id: int
    name: str
    train_id: str
    journey_date: str
    coach: str
    berth_no: int
    berth_type: str
    boarding_station: str
    destination_station: str
    group_id: Optional[int]
    age: int
    needs_lower_berth: bool


def is_vulnerable(p: MatchPassenger) -> bool:
    """Check if passenger is senior citizen (60+) or requires lower berth."""
    return p.age >= 60 or p.needs_lower_berth


def is_berth_compatible_for_vulnerable(
    current_berth_type: str,
    offered_berth_type: str,
) -> bool:
    """Check whether offered berth type is acceptable for a vulnerable passenger.

    R4: Never offer a worse berth type to age 60+ or needs_lower_berth.
    """
    if offered_berth_type in UPPER_CLIMBING_BERTHS:
        return False
    if current_berth_type == "LOWER" and offered_berth_type != "LOWER":
        return False
    return True


def compute_segment_overlap(
    route: List[str],
    req_boarding: str,
    req_destination: str,
    cand_boarding: str,
    cand_destination: str,
) -> Optional[Tuple[str, str, int]]:
    """Compute overlapping train route segment between requester and candidate.

    Returns:
        (start_station, expiry_station, dest_gap) or None if no overlap.
    """
    if not route:
        return None

    route_indices = {stn: i for i, stn in enumerate(route)}

    if req_boarding not in route_indices or req_destination not in route_indices:
        return None
    if cand_boarding not in route_indices or cand_destination not in route_indices:
        return None

    req_b = route_indices[req_boarding]
    req_d = route_indices[req_destination]
    cand_b = route_indices[cand_boarding]
    cand_d = route_indices[cand_destination]

    # Must be valid forward journeys
    if req_b >= req_d or cand_b >= cand_d:
        return None

    start_idx = max(req_b, cand_b)
    expiry_idx = min(req_d, cand_d)

    # Exclude if no overlapping segment
    if start_idx >= expiry_idx:
        return None

    start_station = route[start_idx]
    expiry_station = route[expiry_idx]
    dest_gap = abs(cand_d - req_d)

    return (start_station, expiry_station, dest_gap)


def calculate_berth_distance(
    candidate: MatchPassenger,
    requester: MatchPassenger,
    family_members: List[MatchPassenger],
) -> int:
    """Calculate distance to requester or nearest family member in the target coach."""
    # Target reference berths: family members in candidate's coach (e.g. Meera in S2)
    same_coach_family = [
        m.berth_no for m in family_members if m.coach == candidate.coach
    ]

    if same_coach_family:
        return min(abs(candidate.berth_no - b) for b in same_coach_family)

    if requester.coach == candidate.coach:
        return abs(candidate.berth_no - requester.berth_no)

    all_family = [m.berth_no for m in family_members]
    if all_family:
        return min(abs(candidate.berth_no - b) for b in all_family)

    return abs(candidate.berth_no - requester.berth_no)


def evaluate_candidate(
    candidate: MatchPassenger,
    requester: MatchPassenger,
    family_members: List[MatchPassenger],
    route: List[str],
    excluded_candidate_ids: Set[int],
) -> Optional[Dict[str, Any]]:
    """Pure evaluation of a single co-passenger candidate against business rules.

    Returns candidate match dict or None if ineligible.
    """
    # 1. Self and active exchanges exclusion
    if candidate.id == requester.id:
        return None
    if candidate.id in excluded_candidate_ids:
        return None

    # 2. Train and journey date matching
    if candidate.train_id != requester.train_id:
        return None
    if candidate.journey_date != requester.journey_date:
        return None

    # 3. Same family group exclusion
    if requester.group_id is not None and candidate.group_id == requester.group_id:
        return None

    # 4. Overlapping segment check
    overlap = compute_segment_overlap(
        route=route,
        req_boarding=requester.boarding_station,
        req_destination=requester.destination_station,
        cand_boarding=candidate.boarding_station,
        cand_destination=candidate.destination_station,
    )
    if not overlap:
        return None

    start_station, expiry_station, dest_gap = overlap

    # 5. Destination gap limit (max 3 stops difference along route)
    if dest_gap > 3:
        return None

    # 6. Vulnerable passenger berth protection (R4)
    # Check candidate protection:
    if is_vulnerable(candidate):
        if not is_berth_compatible_for_vulnerable(candidate.berth_type, requester.berth_type):
            return None

    # Check requester protection:
    if is_vulnerable(requester):
        if not is_berth_compatible_for_vulnerable(requester.berth_type, candidate.berth_type):
            return None

    # 7. Categorization
    if dest_gap == 0:
        category = "BEST"
        why = (
            f"Same destination ({requester.destination_station}) and exact feasible segment "
            f"from {start_station} to {expiry_station}."
        )
    else:
        category = "POSSIBLE"
        why = (
            f"Destination differs by {dest_gap} stop(s) ({candidate.destination_station} vs "
            f"{requester.destination_station}); exchange feasible from {start_station} until {expiry_station}."
        )

    # 8. Distance & Proximity scoring
    same_coach = (candidate.coach == requester.coach) or any(
        m.coach == candidate.coach for m in family_members
    )
    berth_distance = calculate_berth_distance(candidate, requester, family_members)

    score = 100
    if not (candidate.coach == requester.coach):
        score -= 20
    score -= min(30, berth_distance)
    score -= (dest_gap * 10)
    proximity_score = max(5, score)

    first_name = candidate.name.strip().split()[0]

    return {
        "candidate_id": candidate.id,
        "first_name": first_name,
        "coach": candidate.coach,
        "berth_no": candidate.berth_no,
        "berth_type": candidate.berth_type,
        "category": category,
        "segment": {"start": start_station, "end": expiry_station},
        "proximity_score": proximity_score,
        "reason": why,
        "why": why,
        "distance_to_requester": berth_distance,
        "destination_gap": dest_gap,
        "same_coach": same_coach,
    }


def find_matches_pure(
    requester: MatchPassenger,
    family_members: List[MatchPassenger],
    candidates: List[MatchPassenger],
    route: List[str],
    excluded_candidate_ids: Optional[Set[int]] = None,
) -> List[Dict[str, Any]]:
    """Pure matching function ranking candidates by category, coach, berth distance, gap."""
    if excluded_candidate_ids is None:
        excluded_candidate_ids = set()

    matches = []
    for cand in candidates:
        eval_result = evaluate_candidate(
            candidate=cand,
            requester=requester,
            family_members=family_members,
            route=route,
            excluded_candidate_ids=excluded_candidate_ids,
        )
        if eval_result:
            matches.append(eval_result)

    # Ranking:
    # 1. Best before Possible
    # 2. Same coach first
    # 3. Smaller berth distance
    # 4. Smaller destination gap
    # 5. Higher proximity score
    def sort_key(item: Dict[str, Any]):
        cat_order = 0 if item["category"] == "BEST" else 1
        coach_order = 0 if item["same_coach"] else 1
        return (
            cat_order,
            coach_order,
            item["distance_to_requester"],
            item["destination_gap"],
            -item["proximity_score"],
            item["candidate_id"],
        )

    matches.sort(key=sort_key)
    return matches


# ============================================================================
# Database Adapter
# ============================================================================

def to_match_passenger(p: Passenger) -> MatchPassenger:
    """Convert SQLAlchemy Passenger ORM model to plain MatchPassenger."""
    return MatchPassenger(
        id=p.id,
        name=p.name,
        train_id=p.train_id,
        journey_date=p.journey_date,
        coach=p.coach,
        berth_no=p.berth_no,
        berth_type=p.berth_type,
        boarding_station=p.boarding_station,
        destination_station=p.destination_station,
        group_id=p.group_id,
        age=p.age,
        needs_lower_berth=p.needs_lower_berth,
    )


async def find_matches_for_passenger(
    db: AsyncSession,
    passenger_id: int,
    need: str = "sit_together",
) -> MatchListResponse:
    """Thin database adapter loading passenger context and executing matching."""
    # 1. Fetch requester with train and group
    requester = await db.scalar(
        select(Passenger)
        .options(selectinload(Passenger.train), selectinload(Passenger.group))
        .where(Passenger.id == passenger_id)
    )
    if not requester:
        raise ValueError(f"Passenger {passenger_id} not found")

    # 2. Fetch family members if in group
    family_members: List[MatchPassenger] = []
    if requester.group_id:
        family_stmt = select(Passenger).where(
            Passenger.group_id == requester.group_id,
            Passenger.id != requester.id,
            Passenger.journey_date == requester.journey_date,
        )
        family_results = (await db.scalars(family_stmt)).all()
        family_members = [to_match_passenger(f) for f in family_results]

    # 3. Fetch all potential co-passengers on the same train and journey date
    cand_stmt = select(Passenger).where(
        Passenger.train_id == requester.train_id,
        Passenger.journey_date == requester.journey_date,
        Passenger.id != requester.id,
    )
    all_candidates_orm = (await db.scalars(cand_stmt)).all()
    all_candidates = [to_match_passenger(c) for c in all_candidates_orm]

    # 4. Exclude passengers already in accepted or active exchanges
    active_stmt = select(ExchangeRequest).where(
        ExchangeRequest.status.in_([
            RequestStatus.ACCEPTED_BY_PASSENGER.value,
            RequestStatus.TTE_APPROVED.value,
        ])
    )
    active_requests = (await db.scalars(active_stmt)).all()
    excluded_ids: Set[int] = set()
    for req in active_requests:
        excluded_ids.add(req.requester_id)
        excluded_ids.add(req.target_id)

    # 5. Route stations
    route = requester.train.route_stations if requester.train else []

    # 6. Run pure matching algorithm
    req_plain = to_match_passenger(requester)
    raw_matches = find_matches_pure(
        requester=req_plain,
        family_members=family_members,
        candidates=all_candidates,
        route=route,
        excluded_candidate_ids=excluded_ids,
    )

    candidates_pydantic: List[MatchCandidate] = []
    best_matches: List[MatchCandidate] = []
    possible_matches: List[MatchCandidate] = []

    for item in raw_matches:
        candidate_obj = MatchCandidate(
            candidate_id=item["candidate_id"],
            first_name=item["first_name"],
            coach=item["coach"],
            berth_no=item["berth_no"],
            berth_type=item["berth_type"],
            category=item["category"],
            segment=JourneySegment(**item["segment"]),
            proximity_score=item["proximity_score"],
            reason=item["reason"],
            why=item["why"],
            distance_to_requester=item["distance_to_requester"],
            destination_gap=item["destination_gap"],
        )
        candidates_pydantic.append(candidate_obj)
        if item["category"] == "BEST":
            best_matches.append(candidate_obj)
        else:
            possible_matches.append(candidate_obj)

    return MatchListResponse(
        requester_coach=requester.coach,
        requester_berth_no=requester.berth_no,
        requester_berth_type=requester.berth_type,
        requester_segment=JourneySegment(
            start=requester.boarding_station,
            end=requester.destination_station,
        ),
        need=need,
        total_candidates=len(candidates_pydantic),
        best_matches=best_matches,
        possible_matches=possible_matches,
        candidates=candidates_pydantic,
    )
