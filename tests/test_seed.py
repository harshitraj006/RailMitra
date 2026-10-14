"""Comprehensive test suite for seed dataset and app health check."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal, init_db
from app.main import app
from app.models import AuditLog, Group, Passenger, Train
from app.seed import get_default_journey_date, reset_database, seed_database


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Ensure database schema is created and freshly seeded before tests."""
    await init_db()
    async with AsyncSessionLocal() as session:
        await reset_database(session)
    yield


@pytest.mark.asyncio
async def test_health_check_endpoint():
    """Test the /health endpoint for correct status and error shape compliance."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["app"] == "RailMitra"
        assert data["database_connected"] is True
        assert data["demo_mode"] is True
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_standardized_error_format_404():
    """Test that nonexistent routes return standard {detail, code} error shape."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/nonexistent-endpoint")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "code" in data
        assert data["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_seed_counts_and_train_routes():
    """Test total seed passengers count and train route sequences."""
    async with AsyncSessionLocal() as session:
        trains = (await session.scalars(select(Train))).all()
        assert len(trains) == 2

        t101 = next(t for t in trains if t.id == "T-101")
        assert t101.name == "Demo Express"
        assert t101.route_stations == ["S1", "S2", "S3", "S4", "S5"]

        t202 = next(t for t in trains if t.id == "T-202")
        assert t202.name == "Return Express"
        assert t202.route_stations == ["S5", "S4", "S3", "S2", "S1"]

        passengers = (await session.scalars(select(Passenger))).all()
        # Expecting approximately 35 passengers
        assert len(passengers) >= 30
        assert len(passengers) <= 40


@pytest.mark.asyncio
async def test_worked_example_asha_and_meera():
    """Verify Asha and Meera's family booking facts exactly as specified."""
    async with AsyncSessionLocal() as session:
        asha = await session.scalar(
            select(Passenger)
            .options(selectinload(Passenger.group))
            .where(Passenger.pnr == "PNR1000001")
        )
        assert asha is not None
        assert asha.name == "Asha Sharma"
        assert asha.coach == "S2"
        assert asha.berth_no == 14
        assert asha.berth_type == "UPPER"
        assert asha.boarding_station == "S1"
        assert asha.destination_station == "S4"
        assert asha.group is not None
        assert asha.group.name == "Asha's family"

        meera = await session.scalar(
            select(Passenger)
            .options(selectinload(Passenger.group))
            .where(Passenger.pnr == "PNR1000002")
        )
        assert meera is not None
        assert meera.name == "Meera Sharma"
        assert meera.age == 62
        assert meera.coach == "S2"
        assert meera.berth_no == 41
        assert meera.berth_type == "LOWER"
        assert meera.needs_lower_berth is True
        assert meera.boarding_station == "S1"
        assert meera.destination_station == "S4"
        assert meera.group_id == asha.group_id


@pytest.mark.asyncio
async def test_worked_example_target_candidates():
    """Verify Kiran, Ravi, Vikram, Neha, Sunita attributes."""
    async with AsyncSessionLocal() as session:
        # Kiran: Berth 43, UPPER, S1->S4 (BEST MATCH)
        kiran = await session.scalar(select(Passenger).where(Passenger.pnr == "PNR1000003"))
        assert kiran is not None
        assert kiran.name == "Kiran Patel"
        assert kiran.coach == "S2"
        assert kiran.berth_no == 43
        assert kiran.berth_type == "UPPER"
        assert kiran.boarding_station == "S1"
        assert kiran.destination_station == "S4"

        # Ravi: Berth 46, LOWER, S1->S5 (POSSIBLE MATCH)
        ravi = await session.scalar(select(Passenger).where(Passenger.pnr == "PNR1000004"))
        assert ravi is not None
        assert ravi.name == "Ravi Verma"
        assert ravi.coach == "S2"
        assert ravi.berth_no == 46
        assert ravi.berth_type == "LOWER"
        assert ravi.boarding_station == "S1"
        assert ravi.destination_station == "S5"

        # Vikram: Berth 50, S1->S3 (exchange expires at S3)
        vikram = await session.scalar(select(Passenger).where(Passenger.pnr == "PNR1000005"))
        assert vikram is not None
        assert vikram.coach == "S2"
        assert vikram.berth_no == 50
        assert vikram.boarding_station == "S1"
        assert vikram.destination_station == "S3"

        # Neha: S2->S4
        neha = await session.scalar(select(Passenger).where(Passenger.pnr == "PNR1000006"))
        assert neha is not None
        assert neha.coach == "S2"
        assert neha.berth_no == 25
        assert neha.boarding_station == "S2"
        assert neha.destination_station == "S4"

        # Sunita: S3->S5
        sunita = await session.scalar(select(Passenger).where(Passenger.pnr == "PNR1000007"))
        assert sunita is not None
        assert sunita.coach == "S2"
        assert sunita.berth_no == 32
        assert sunita.boarding_station == "S3"
        assert sunita.destination_station == "S5"


@pytest.mark.asyncio
async def test_verma_family_group_of_5():
    """Verify second family of 5 split across coaches S1 and S3."""
    async with AsyncSessionLocal() as session:
        group = await session.scalar(
            select(Group)
            .options(selectinload(Group.passengers))
            .where(Group.name == "Verma Family")
        )
        assert group is not None
        assert len(group.passengers) == 5

        coaches = {p.coach for p in group.passengers}
        assert coaches == {"S1", "S3"}

        s1_members = [p for p in group.passengers if p.coach == "S1"]
        s3_members = [p for p in group.passengers if p.coach == "S3"]
        assert len(s1_members) == 3
        assert len(s3_members) == 2

        # Check senior citizen needs_lower_berth flag
        dadi = next(p for p in group.passengers if p.name == "Dadi Devi")
        assert dadi.age == 74
        assert dadi.needs_lower_berth is True
        assert dadi.berth_type == "LOWER"


@pytest.mark.asyncio
async def test_out_of_scope_passengers_exclusion_boundaries():
    """Verify passengers with different train or date exist but won't match."""
    async with AsyncSessionLocal() as session:
        # Different train
        diff_train = await session.scalar(select(Passenger).where(Passenger.pnr == "PNR1000098"))
        assert diff_train is not None
        assert diff_train.train_id == "T-202"
        assert diff_train.train_id != "T-101"

        # Different date
        today = get_default_journey_date()
        diff_date = await session.scalar(select(Passenger).where(Passenger.pnr == "PNR1000099"))
        assert diff_date is not None
        assert diff_date.journey_date != today


@pytest.mark.asyncio
async def test_tte_initial_audit_log():
    """Verify TTE user 'tte_demo' has an initial system audit entry."""
    async with AsyncSessionLocal() as session:
        audit = await session.scalar(
            select(AuditLog).where(AuditLog.actor == "tte_demo")
        )
        assert audit is not None
        assert audit.action == "SYSTEM_INIT"


@pytest.mark.asyncio
async def test_idempotent_seeding():
    """Verify calling seed_database multiple times without force does not duplicate data."""
    async with AsyncSessionLocal() as session:
        count_before = len((await session.scalars(select(Passenger))).all())
        result = await seed_database(session, force=False)
        assert result["seeded"] is False
        count_after = len((await session.scalars(select(Passenger))).all())
        assert count_after == count_before
