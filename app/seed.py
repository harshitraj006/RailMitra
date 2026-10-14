"""Seed data module for RailMitra simulated reservation system.

Includes:
- Train T-101 "Demo Express" (route: S1 -> S2 -> S3 -> S4 -> S5)
- Train T-202 "Return Express" (out-of-scope train)
- Asha & Meera worked-example family (Asha S2-14, Meera S2-41 age 62)
- Kiran (S2-43 BEST MATCH)
- Ravi (S2-46 POSSIBLE MATCH)
- Vikram (S2-50 expires at S3)
- Neha (S2-25) & Sunita (S2-32 minimal overlap)
- Second family of 5 split across S1 and S3 (Verma Family)
- Total ~35 passengers with realistic berths and fake masked contacts
- Out-of-scope passenger on train T-202
- Out-of-scope passenger on future journey date
- TTE user 'tte_demo'
"""

from datetime import datetime, timezone
import hashlib
from typing import List, Tuple
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditLog,
    BerthType,
    Confirmation,
    ExchangeRequest,
    Group,
    GroupRequest,
    Notification,
    OTPCode,
    Passenger,
    Session,
    TTEReview,
    Train,
    utc_now,
)


def get_default_journey_date() -> str:
    """Return today's date formatted as YYYY-MM-DD in UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def hash_otp(code: str) -> str:
    """Hash simulated OTP using SHA-256."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


# Route definition for Train T-101
DEMO_ROUTE = ["S1", "S2", "S3", "S4", "S5"]
REVERSE_ROUTE = ["S5", "S4", "S3", "S2", "S1"]


async def reset_database(db: AsyncSession) -> dict:
    """Completely wipe and reseed the database to the default initial state."""
    # Delete children in reverse dependency order
    await db.execute(delete(Confirmation))
    await db.execute(delete(TTEReview))
    await db.execute(delete(ExchangeRequest))
    await db.execute(delete(GroupRequest))
    await db.execute(delete(AuditLog))
    await db.execute(delete(Notification))
    await db.execute(delete(Session))
    await db.execute(delete(OTPCode))
    await db.execute(delete(Passenger))
    await db.execute(delete(Group))
    await db.execute(delete(Train))
    await db.commit()

    return await seed_database(db, force=True)


async def seed_database(db: AsyncSession, force: bool = False) -> dict:
    """Seed initial reservation dataset idempotently.

    If data is already present and force=False, returns existing counts without modifying.
    """
    # Check if already seeded
    existing_train = await db.scalar(select(Train).where(Train.id == "T-101"))
    if existing_train and not force:
        passengers_count = await db.scalar(select(Passenger.id).order_by(Passenger.id.desc())) or 0
        return {
            "seeded": False,
            "message": "Database already populated.",
            "passengers_count": passengers_count,
        }

    journey_date = get_default_journey_date()

    # 1. Trains
    train_t101 = Train(
        id="T-101",
        number="12951",
        name="Demo Express",
        route_stations=DEMO_ROUTE,
    )
    train_t202 = Train(
        id="T-202",
        number="12952",
        name="Return Express",
        route_stations=REVERSE_ROUTE,
    )
    db.add_all([train_t101, train_t202])
    await db.flush()

    # 2. Groups
    asha_group = Group(name="Asha's family")
    verma_group = Group(name="Verma Family")
    db.add_all([asha_group, verma_group])
    await db.flush()

    # 3. Passengers
    passengers: List[Passenger] = []

    # Worked Example 1: Asha's Family
    # - Asha: Coach S2, Berth 14, UPPER, S1->S4
    asha = Passenger(
        pnr="PNR1000001",
        name="Asha Sharma",
        phone_masked="+91-98****1201",
        email_masked="as****@example.com",
        train_id="T-101",
        journey_date=journey_date,
        coach="S2",
        berth_no=14,
        berth_type=BerthType.UPPER.value,
        boarding_station="S1",
        destination_station="S4",
        group_id=asha_group.id,
        age=34,
        needs_lower_berth=False,
    )
    # - Meera (mother, age 62): Coach S2, Berth 41, LOWER, S1->S4
    meera = Passenger(
        pnr="PNR1000002",
        name="Meera Sharma",
        phone_masked="+91-98****1202",
        email_masked="me****@example.com",
        train_id="T-101",
        journey_date=journey_date,
        coach="S2",
        berth_no=41,
        berth_type=BerthType.LOWER.value,
        boarding_station="S1",
        destination_station="S4",
        group_id=asha_group.id,
        age=62,
        needs_lower_berth=True,
    )

    # Worked Example 2: Target Co-passengers
    # - Kiran: Berth 43, UPPER, S1->S4 (BEST MATCH for Asha)
    kiran = Passenger(
        pnr="PNR1000003",
        name="Kiran Patel",
        phone_masked="+91-98****1203",
        email_masked="ki****@example.com",
        train_id="T-101",
        journey_date=journey_date,
        coach="S2",
        berth_no=43,
        berth_type=BerthType.UPPER.value,
        boarding_station="S1",
        destination_station="S4",
        group_id=None,
        age=28,
        needs_lower_berth=False,
    )
    # - Ravi: Berth 46, LOWER, S1->S5 (POSSIBLE MATCH for Asha)
    ravi = Passenger(
        pnr="PNR1000004",
        name="Ravi Verma",
        phone_masked="+91-98****1204",
        email_masked="ra****@example.com",
        train_id="T-101",
        journey_date=journey_date,
        coach="S2",
        berth_no=46,
        berth_type=BerthType.LOWER.value,
        boarding_station="S1",
        destination_station="S5",
        group_id=None,
        age=35,
        needs_lower_berth=False,
    )
    # - Vikram: Berth 50, S1->S3 (exchange expires at S3)
    vikram = Passenger(
        pnr="PNR1000005",
        name="Vikram Singh",
        phone_masked="+91-98****1205",
        email_masked="vi****@example.com",
        train_id="T-101",
        journey_date=journey_date,
        coach="S2",
        berth_no=50,
        berth_type=BerthType.UPPER.value,
        boarding_station="S1",
        destination_station="S3",
        group_id=None,
        age=31,
        needs_lower_berth=False,
    )
    # - Neha (S2->S4)
    neha = Passenger(
        pnr="PNR1000006",
        name="Neha Gupta",
        phone_masked="+91-98****1206",
        email_masked="ne****@example.com",
        train_id="T-101",
        journey_date=journey_date,
        coach="S2",
        berth_no=25,
        berth_type=BerthType.MIDDLE.value,
        boarding_station="S2",
        destination_station="S4",
        group_id=None,
        age=29,
        needs_lower_berth=False,
    )
    # - Sunita (S3->S5, minimal overlap with Asha)
    sunita = Passenger(
        pnr="PNR1000007",
        name="Sunita Roy",
        phone_masked="+91-98****1207",
        email_masked="su****@example.com",
        train_id="T-101",
        journey_date=journey_date,
        coach="S2",
        berth_no=32,
        berth_type=BerthType.LOWER.value,
        boarding_station="S3",
        destination_station="S5",
        group_id=None,
        age=40,
        needs_lower_berth=False,
    )

    passengers.extend([asha, meera, kiran, ravi, vikram, neha, sunita])

    # Worked Example 3: Second family of 5 split across coaches S1 and S3
    verma_family_data: List[Tuple[str, str, str, int, str, int, bool]] = [
        ("PNR1000010", "Rajesh Verma", "S1", 10, BerthType.LOWER.value, 52, False),
        ("PNR1000011", "Sunita Verma", "S1", 12, BerthType.UPPER.value, 48, False),
        ("PNR1000012", "Amit Verma", "S1", 15, BerthType.MIDDLE.value, 22, False),
        ("PNR1000013", "Pooja Verma", "S3", 55, BerthType.UPPER.value, 19, False),
        ("PNR1000014", "Dadi Devi", "S3", 58, BerthType.LOWER.value, 74, True),
    ]
    for pnr, name, coach, berth, btype, age, needs_lower in verma_family_data:
        passengers.append(
            Passenger(
                pnr=pnr,
                name=name,
                phone_masked=f"+91-98****{pnr[-4:]}",
                email_masked=f"{name[:2].lower()}****@example.com",
                train_id="T-101",
                journey_date=journey_date,
                coach=coach,
                berth_no=berth,
                berth_type=btype,
                boarding_station="S1",
                destination_station="S5",
                group_id=verma_group.id,
                age=age,
                needs_lower_berth=needs_lower,
            )
        )

    # Additional passengers for variety across S1, S2, S3 to reach ~35 total
    variety_data: List[Tuple[str, str, str, int, str, str, str, int, bool]] = [
        # Coach S1 passengers
        ("PNR1000015", "Manoj Tiwari", "S1", 18, BerthType.LOWER.value, "S1", "S5", 45, False),
        ("PNR1000016", "Geeta Tiwari", "S1", 19, BerthType.MIDDLE.value, "S1", "S5", 42, False),
        ("PNR1000017", "Deepak Joshi", "S1", 22, BerthType.UPPER.value, "S1", "S4", 33, False),
        ("PNR1000018", "Priya Nair", "S1", 25, BerthType.SIDE_LOWER.value, "S2", "S5", 27, False),
        ("PNR1000019", "Ramesh Sen", "S1", 26, BerthType.SIDE_UPPER.value, "S2", "S5", 38, False),
        ("PNR1000020", "Anil Kumar", "S1", 30, BerthType.LOWER.value, "S1", "S3", 65, True),
        ("PNR1000021", "Sunil Yadav", "S1", 35, BerthType.UPPER.value, "S1", "S4", 26, False),

        # Coach S2 passengers
        ("PNR1000022", "Rahul Dravid", "S2", 3, BerthType.LOWER.value, "S1", "S4", 51, False),
        ("PNR1000023", "Sourav Ganguly", "S2", 4, BerthType.MIDDLE.value, "S1", "S4", 52, False),
        ("PNR1000024", "Sachin Tendulkar", "S2", 5, BerthType.UPPER.value, "S1", "S4", 51, False),
        ("PNR1000025", "VVS Laxman", "S2", 7, BerthType.SIDE_LOWER.value, "S2", "S4", 49, False),
        ("PNR1000026", "Harbhajan Singh", "S2", 8, BerthType.SIDE_UPPER.value, "S2", "S5", 44, False),
        ("PNR1000027", "Zaheer Khan", "S2", 38, BerthType.MIDDLE.value, "S1", "S4", 45, False),
        ("PNR1000028", "Yuvraj Singh", "S2", 39, BerthType.UPPER.value, "S1", "S4", 43, False),
        ("PNR1000029", "MS Dhoni", "S2", 42, BerthType.MIDDLE.value, "S1", "S4", 43, False),
        ("PNR1000030", "Suresh Raina", "S2", 47, BerthType.MIDDLE.value, "S1", "S5", 37, False),
        ("PNR1000031", "Rohit Sharma", "S2", 48, BerthType.UPPER.value, "S1", "S5", 37, False),

        # Coach S3 passengers
        ("PNR1000032", "Jasprit Bumrah", "S3", 11, BerthType.LOWER.value, "S1", "S5", 30, False),
        ("PNR1000033", "Mohammed Shami", "S3", 14, BerthType.UPPER.value, "S1", "S5", 34, False),
        ("PNR1000034", "Ravindra Jadeja", "S3", 21, BerthType.SIDE_LOWER.value, "S1", "S4", 35, False),
        ("PNR1000035", "Shikhar Dhawan", "S3", 22, BerthType.SIDE_UPPER.value, "S1", "S4", 38, False),
    ]

    for pnr, name, coach, berth, btype, b_stn, d_stn, age, needs_lower in variety_data:
        passengers.append(
            Passenger(
                pnr=pnr,
                name=name,
                phone_masked=f"+91-98****{pnr[-4:]}",
                email_masked=f"{name[:2].lower()}****@example.com",
                train_id="T-101",
                journey_date=journey_date,
                coach=coach,
                berth_no=berth,
                berth_type=btype,
                boarding_station=b_stn,
                destination_station=d_stn,
                group_id=None,
                age=age,
                needs_lower_berth=needs_lower,
            )
        )

    # Out-of-scope passengers to prove matching boundaries
    # 1. Different train (T-202)
    passengers.append(
        Passenger(
            pnr="PNR1000098",
            name="Arjun Rao",
            phone_masked="+91-98****1098",
            email_masked="ar****@example.com",
            train_id="T-202",
            journey_date=journey_date,
            coach="S2",
            berth_no=14,
            berth_type=BerthType.UPPER.value,
            boarding_station="S5",
            destination_station="S1",
            group_id=None,
            age=29,
            needs_lower_berth=False,
        )
    )

    # 2. Different journey date (future date)
    passengers.append(
        Passenger(
            pnr="PNR1000099",
            name="Kavita Reddy",
            phone_masked="+91-98****1099",
            email_masked="ka****@example.com",
            train_id="T-101",
            journey_date="2026-11-20",
            coach="S2",
            berth_no=44,
            berth_type=BerthType.UPPER.value,
            boarding_station="S1",
            destination_station="S4",
            group_id=None,
            age=33,
            needs_lower_berth=False,
        )
    )

    db.add_all(passengers)
    await db.flush()

    # Seed an initial audit log record marking database initialized with TTE actor
    audit_init = AuditLog(
        entity_type="SYSTEM",
        entity_id=1,
        action="SYSTEM_INIT",
        actor="tte_demo",
        details={
            "description": "Simulated reservation dataset loaded",
            "trains": ["T-101", "T-202"],
            "total_passengers": len(passengers),
            "journey_date": journey_date,
        },
        timestamp=utc_now(),
    )
    db.add(audit_init)
    await db.commit()

    return {
        "seeded": True,
        "message": "Simulated reservation dataset successfully loaded.",
        "passengers_count": len(passengers),
        "trains_count": 2,
        "groups_count": 2,
        "journey_date": journey_date,
    }
