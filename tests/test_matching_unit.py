"""Unit tests for pure matching functions without database dependencies."""

import pytest
from app.services.matching import (
    MatchPassenger,
    compute_segment_overlap,
    evaluate_candidate,
    find_matches_pure,
    is_berth_compatible_for_vulnerable,
    is_vulnerable,
)

ROUTE_5 = ["S1", "S2", "S3", "S4", "S5"]
ROUTE_10 = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10"]


def test_compute_segment_overlap_identical():
    """Identical segments S1->S4 yield exact overlap and 0 destination gap."""
    overlap = compute_segment_overlap(ROUTE_5, "S1", "S4", "S1", "S4")
    assert overlap is not None
    start, expiry, gap = overlap
    assert start == "S1"
    assert expiry == "S4"
    assert gap == 0


def test_compute_segment_overlap_different_destination():
    """S1->S4 vs S1->S5 yields overlap S1->S4 with gap 1."""
    overlap = compute_segment_overlap(ROUTE_5, "S1", "S4", "S1", "S5")
    assert overlap is not None
    start, expiry, gap = overlap
    assert start == "S1"
    assert expiry == "S4"
    assert gap == 1


def test_compute_segment_overlap_earlier_candidate_destination():
    """S1->S4 vs S1->S3 yields expiry at earlier station S3 with gap 1."""
    overlap = compute_segment_overlap(ROUTE_5, "S1", "S4", "S1", "S3")
    assert overlap is not None
    start, expiry, gap = overlap
    assert start == "S1"
    assert expiry == "S3"
    assert gap == 1


def test_compute_segment_overlap_no_overlap():
    """S1->S2 vs S3->S5 have no overlapping journey segment."""
    overlap = compute_segment_overlap(ROUTE_5, "S1", "S2", "S3", "S5")
    assert overlap is None


def test_compute_segment_overlap_touching_station_only():
    """S1->S2 and S2->S4 touch at S2 but do not share any travel segment."""
    overlap = compute_segment_overlap(ROUTE_5, "S1", "S2", "S2", "S4")
    assert overlap is None


def test_destination_gap_greater_than_3_excluded():
    """A candidate with destination gap > 3 stops along route is excluded."""
    requester = MatchPassenger(
        id=1,
        name="Requester",
        train_id="T-101",
        journey_date="2026-10-14",
        coach="S1",
        berth_no=10,
        berth_type="UPPER",
        boarding_station="S1",
        destination_station="S2",
        group_id=None,
        age=30,
        needs_lower_berth=False,
    )
    # Candidate travelling S1 -> S7 (gap = 5 stops)
    candidate = MatchPassenger(
        id=2,
        name="Candidate Far",
        train_id="T-101",
        journey_date="2026-10-14",
        coach="S1",
        berth_no=12,
        berth_type="UPPER",
        boarding_station="S1",
        destination_station="S7",
        group_id=None,
        age=30,
        needs_lower_berth=False,
    )

    res = evaluate_candidate(
        candidate=candidate,
        requester=requester,
        family_members=[],
        route=ROUTE_10,
        excluded_candidate_ids=set(),
    )
    assert res is None  # Gap > 3 must be excluded


def test_vulnerable_berth_compatibility_logic():
    """Verify berth rules protecting vulnerable passengers."""
    # Lower is premier
    assert is_berth_compatible_for_vulnerable("LOWER", "LOWER") is True
    assert is_berth_compatible_for_vulnerable("LOWER", "UPPER") is False
    assert is_berth_compatible_for_vulnerable("LOWER", "MIDDLE") is False
    assert is_berth_compatible_for_vulnerable("LOWER", "SIDE_UPPER") is False
    assert is_berth_compatible_for_vulnerable("LOWER", "SIDE_LOWER") is False

    # Upper/Middle/Side Upper climbing berths are never acceptable for vulnerable passengers
    assert is_berth_compatible_for_vulnerable("MIDDLE", "UPPER") is False
    assert is_berth_compatible_for_vulnerable("SIDE_LOWER", "UPPER") is False


def test_meera_protected_berth_rule():
    """Meera (age 62, LOWER berth) is never swapped into UPPER/MIDDLE berth."""
    meera = MatchPassenger(
        id=2,
        name="Meera Sharma",
        train_id="T-101",
        journey_date="2026-10-14",
        coach="S2",
        berth_no=41,
        berth_type="LOWER",
        boarding_station="S1",
        destination_station="S4",
        group_id=1,
        age=62,
        needs_lower_berth=True,
    )
    upper_candidate = MatchPassenger(
        id=3,
        name="Kiran Patel",
        train_id="T-101",
        journey_date="2026-10-14",
        coach="S2",
        berth_no=43,
        berth_type="UPPER",
        boarding_station="S1",
        destination_station="S4",
        group_id=None,
        age=28,
        needs_lower_berth=False,
    )

    # When Meera is the requester, she cannot be offered an UPPER berth
    res = evaluate_candidate(
        candidate=upper_candidate,
        requester=meera,
        family_members=[],
        route=ROUTE_5,
        excluded_candidate_ids=set(),
    )
    assert res is None

    # When Meera is the candidate and an UPPER berth is offered to her, she is excluded
    asha = MatchPassenger(
        id=1,
        name="Asha Sharma",
        train_id="T-101",
        journey_date="2026-10-14",
        coach="S2",
        berth_no=14,
        berth_type="UPPER",
        boarding_station="S1",
        destination_station="S4",
        group_id=None,  # test as if not in same group
        age=34,
        needs_lower_berth=False,
    )
    res_offer_to_meera = evaluate_candidate(
        candidate=meera,
        requester=asha,
        family_members=[],
        route=ROUTE_5,
        excluded_candidate_ids=set(),
    )
    assert res_offer_to_meera is None


def test_asha_worked_example_ranking():
    """Verify Asha's ranking: Kiran is BEST MATCH and Ravi is POSSIBLE MATCH."""
    asha = MatchPassenger(
        id=1,
        name="Asha Sharma",
        train_id="T-101",
        journey_date="2026-10-14",
        coach="S2",
        berth_no=14,
        berth_type="UPPER",
        boarding_station="S1",
        destination_station="S4",
        group_id=1,
        age=34,
        needs_lower_berth=False,
    )
    meera = MatchPassenger(
        id=2,
        name="Meera Sharma",
        train_id="T-101",
        journey_date="2026-10-14",
        coach="S2",
        berth_no=41,
        berth_type="LOWER",
        boarding_station="S1",
        destination_station="S4",
        group_id=1,
        age=62,
        needs_lower_berth=True,
    )
    kiran = MatchPassenger(
        id=3,
        name="Kiran Patel",
        train_id="T-101",
        journey_date="2026-10-14",
        coach="S2",
        berth_no=43,
        berth_type="UPPER",
        boarding_station="S1",
        destination_station="S4",
        group_id=None,
        age=28,
        needs_lower_berth=False,
    )
    ravi = MatchPassenger(
        id=4,
        name="Ravi Verma",
        train_id="T-101",
        journey_date="2026-10-14",
        coach="S2",
        berth_no=46,
        berth_type="LOWER",
        boarding_station="S1",
        destination_station="S5",
        group_id=None,
        age=35,
        needs_lower_berth=False,
    )
    diff_train = MatchPassenger(
        id=98,
        name="Arjun Rao",
        train_id="T-202",
        journey_date="2026-10-14",
        coach="S2",
        berth_no=43,
        berth_type="UPPER",
        boarding_station="S5",
        destination_station="S1",
        group_id=None,
        age=29,
        needs_lower_berth=False,
    )

    candidates = [kiran, ravi, meera, diff_train]
    matches = find_matches_pure(
        requester=asha,
        family_members=[meera],
        candidates=candidates,
        route=ROUTE_5,
        excluded_candidate_ids=set(),
    )

    # Out of scope passenger and Meera (same group) must be excluded
    candidate_ids = [m["candidate_id"] for m in matches]
    assert 2 not in candidate_ids  # Meera excluded
    assert 98 not in candidate_ids  # T-202 excluded

    # Kiran must be first (BEST), Ravi second (POSSIBLE)
    assert matches[0]["candidate_id"] == 3
    assert matches[0]["category"] == "BEST"
    assert matches[0]["first_name"] == "Kiran"
    assert matches[0]["distance_to_requester"] == 2  # |43 - 41| (to mother Meera)
    assert matches[0]["destination_gap"] == 0

    assert matches[1]["candidate_id"] == 4
    assert matches[1]["category"] == "POSSIBLE"
    assert matches[1]["first_name"] == "Ravi"
    assert matches[1]["destination_gap"] == 1
