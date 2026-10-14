"""Integration tests for RailMitra Part 2 core engine APIs.

Covers:
- Journey validation against simulated dataset
- OTP dispatch, attempts counting, 10-minute lockout (HTTP 423), and session generation
- Session isolation (Passenger A cannot act as B)
- Pure matching engine via /api/match with privacy guarantees and performance < 500ms
- Meera's protected berth rule (no worse berth swaps)
- 3-request journey cap (HTTP 429) and duplicate target prevention (HTTP 409)
"""

import time
from datetime import timedelta
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.database import AsyncSessionLocal, init_db
from app.main import app
from app.models import AuditLog, ExchangeRequest, OTPCode, Passenger, RequestStatus, Session, utc_now
from app.seed import get_default_journey_date, reset_database


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Ensure database schema is created and freshly seeded before each test."""
    await init_db()
    async with AsyncSessionLocal() as session:
        await reset_database(session)
    yield


@pytest.mark.asyncio
async def test_journey_validate_success_and_errors():
    """Test journey validation against simulated dataset with route and group info."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        today = get_default_journey_date()

        # 1. Successful validation for Asha
        res = await client.post(
            "/api/journey/validate",
            json={"pnr": "PNR1000001", "train_number": "12951", "date": today},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["pnr"] == "PNR1000001"
        assert data["passenger_name"] == "Asha Sharma"
        assert data["coach"] == "S2"
        assert data["berth_no"] == 14
        assert data["berth_type"] == "UPPER"
        assert data["route"] == ["S1", "S2", "S3", "S4", "S5"]
        assert data["group_name"] == "Asha's family"
        assert len(data["group_members"]) == 1
        assert data["group_members"][0]["name"] == "Meera Sharma"
        assert data["group_members"][0]["berth_no"] == 41
        assert "disclaimer" in data

        # 2. Non-existent PNR -> 404
        res_404 = await client.post(
            "/api/journey/validate",
            json={"pnr": "PNR9999999"},
        )
        assert res_404.status_code == 404
        assert res_404.json()["code"] == "PNR_NOT_FOUND"

        # 3. Train mismatch -> 400
        res_train_err = await client.post(
            "/api/journey/validate",
            json={"pnr": "PNR1000001", "train_number": "99999"},
        )
        assert res_train_err.status_code == 400
        assert res_train_err.json()["code"] == "TRAIN_MISMATCH"

        # 4. Date mismatch -> 400
        res_date_err = await client.post(
            "/api/journey/validate",
            json={"pnr": "PNR1000001", "date": "2030-01-01"},
        )
        assert res_date_err.status_code == 400
        assert res_date_err.json()["code"] == "DATE_MISMATCH"


@pytest.mark.asyncio
async def test_otp_dispatch_attempts_lockout_and_sessions():
    """Test OTP dispatch, 3-attempt limit, 10-minute lockout (HTTP 423), and session creation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Request OTP for Asha
        send_res = await client.post("/api/otp/send", json={"pnr": "PNR1000001"})
        assert send_res.status_code == 200
        send_data = send_res.json()
        assert send_data["success"] is True
        assert "masked_phone" in send_data
        demo_otp = send_data.get("demo_otp")
        assert demo_otp is not None
        assert len(demo_otp) == 6

        # 2. Attempt 1 with invalid code -> 400 INVALID_OTP (2 remaining)
        res_bad1 = await client.post("/api/otp/verify", json={"pnr": "PNR1000001", "code": "000000"})
        assert res_bad1.status_code == 400
        assert res_bad1.json()["code"] == "INVALID_OTP"
        assert "2 attempt(s) remaining" in res_bad1.json()["detail"]

        # 3. Attempt 2 with invalid code -> 400 INVALID_OTP (1 remaining)
        res_bad2 = await client.post("/api/otp/verify", json={"pnr": "PNR1000001", "code": "111111"})
        assert res_bad2.status_code == 400
        assert res_bad2.json()["code"] == "INVALID_OTP"
        assert "1 attempt(s) remaining" in res_bad2.json()["detail"]

        # 4. Attempt 3 with invalid code -> 423 ACCOUNT_LOCKED (10 min lockout)
        res_bad3 = await client.post("/api/otp/verify", json={"pnr": "PNR1000001", "code": "222222"})
        assert res_bad3.status_code == 423
        assert res_bad3.json()["code"] == "ACCOUNT_LOCKED"
        assert "Account locked for 10 minutes" in res_bad3.json()["detail"]

        # 5. Subsequent attempts during lockout return 423 with seconds remaining
        res_locked = await client.post("/api/otp/verify", json={"pnr": "PNR1000001", "code": demo_otp})
        assert res_locked.status_code == 423
        assert res_locked.json()["code"] == "ACCOUNT_LOCKED"

        # Subsequent send_otp during lockout is also blocked with 423
        res_send_locked = await client.post("/api/otp/send", json={"pnr": "PNR1000001"})
        assert res_send_locked.status_code == 423
        assert res_send_locked.json()["code"] == "ACCOUNT_LOCKED"


@pytest.mark.asyncio
async def test_otp_expiration():
    """Verify expired OTP code is rejected with 400 OTP_EXPIRED."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Send OTP for Kiran
        send_res = await client.post("/api/otp/send", json={"pnr": "PNR1000003"})
        demo_otp = send_res.json()["demo_otp"]

        # Simulate expiration by rolling back expires_at in database
        async with AsyncSessionLocal() as session:
            kiran = await session.scalar(select(Passenger).where(Passenger.pnr == "PNR1000003"))
            otp_record = await session.scalar(
                select(OTPCode)
                .where(OTPCode.passenger_id == kiran.id, OTPCode.verified.is_(False))
                .order_by(OTPCode.id.desc())
            )
            otp_record.expires_at = utc_now() - timedelta(minutes=10)
            await session.commit()

        # Attempt verification with expired code
        res_exp = await client.post("/api/otp/verify", json={"pnr": "PNR1000003", "code": demo_otp})
        assert res_exp.status_code == 400
        assert res_exp.json()["code"] == "OTP_EXPIRED"


@pytest.mark.asyncio
async def test_session_isolation_and_logout():
    """Verify that one session token = one passenger and Passenger A cannot act as B."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Authenticate Kiran (PNR1000003)
        res_kiran_otp = await client.post("/api/otp/send", json={"pnr": "PNR1000003"})
        kiran_code = res_kiran_otp.json()["demo_otp"]
        verify_kiran = await client.post("/api/otp/verify", json={"pnr": "PNR1000003", "code": kiran_code})
        kiran_token = verify_kiran.json()["session_token"]

        # Authenticate Ravi (PNR1000004)
        res_ravi_otp = await client.post("/api/otp/send", json={"pnr": "PNR1000004"})
        ravi_code = res_ravi_otp.json()["demo_otp"]
        verify_ravi = await client.post("/api/otp/verify", json={"pnr": "PNR1000004", "code": ravi_code})
        ravi_token = verify_ravi.json()["session_token"]

        # Kiran's token returns Kiran's profile
        res_me_kiran = await client.get("/api/me", headers={"X-Session-Token": kiran_token})
        assert res_me_kiran.status_code == 200
        assert res_me_kiran.json()["pnr"] == "PNR1000003"
        assert res_me_kiran.json()["name"] == "Kiran Patel"

        # Ravi's token returns Ravi's profile
        res_me_ravi = await client.get("/api/me", headers={"X-Session-Token": ravi_token})
        assert res_me_ravi.status_code == 200
        assert res_me_ravi.json()["pnr"] == "PNR1000004"
        assert res_me_ravi.json()["name"] == "Ravi Verma"

        # Missing token -> 401 UNAUTHORIZED
        res_no_token = await client.get("/api/me")
        assert res_no_token.status_code == 401
        assert res_no_token.json()["code"] == "UNAUTHORIZED"

        # Invalid token -> 401 INVALID_SESSION
        res_fake_token = await client.get("/api/me", headers={"X-Session-Token": "invalid-token-123"})
        assert res_fake_token.status_code == 401
        assert res_fake_token.json()["code"] == "INVALID_SESSION"

        # Logout Kiran
        logout_res = await client.post("/api/logout", headers={"X-Session-Token": kiran_token})
        assert logout_res.status_code == 200

        # Post-logout: Kiran's token is revoked
        res_revoked = await client.get("/api/me", headers={"X-Session-Token": kiran_token})
        assert res_revoked.status_code == 401


@pytest.mark.asyncio
async def test_matching_endpoint_privacy_and_performance():
    """Verify /api/match returns correct ranking, privacy preservation, and response time < 500ms."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Authenticate as Asha (PNR1000001)
        send_res = await client.post("/api/otp/send", json={"pnr": "PNR1000001"})
        code = send_res.json()["demo_otp"]
        verify_res = await client.post("/api/otp/verify", json={"pnr": "PNR1000001", "code": code})
        token = verify_res.json()["session_token"]

        # Measure response time on seed dataset
        t_start = time.perf_counter()
        match_res = await client.get("/api/match", headers={"X-Session-Token": token})
        duration_ms = (time.perf_counter() - t_start) * 1000

        assert match_res.status_code == 200
        assert duration_ms < 500, f"Match response time was {duration_ms:.2f} ms (expected < 500 ms)"

        data = match_res.json()
        candidates = data["candidates"]
        best_matches = data["best_matches"]
        possible_matches = data["possible_matches"]

        assert len(best_matches) >= 1
        assert len(possible_matches) >= 1

        # 1. Kiran is the first candidate and a BEST MATCH
        kiran_match = candidates[0]
        assert kiran_match["first_name"] == "Kiran"
        assert kiran_match["coach"] == "S2"
        assert kiran_match["berth_no"] == 43
        assert kiran_match["category"] == "BEST"
        assert kiran_match["destination_gap"] == 0
        assert kiran_match["distance_to_requester"] == 2  # |43 - 41| (to mother Meera)
        assert kiran_match["segment"]["start"] == "S1"
        assert kiran_match["segment"]["end"] == "S4"

        # 2. Ravi is present as a POSSIBLE MATCH
        ravi_match = next((c for c in candidates if c["first_name"] == "Ravi"), None)
        assert ravi_match is not None
        assert ravi_match["category"] == "POSSIBLE"
        assert ravi_match["destination_gap"] == 1
        assert ravi_match["segment"]["end"] == "S4"  # Expiry at earlier destination S4

        # 3. Privacy compliance: PNR, phone, and email must NEVER be in candidate objects
        for c in candidates:
            assert "pnr" not in c
            assert "phone" not in c
            assert "phone_masked" not in c
            assert "email" not in c
            assert "email_masked" not in c
            # Only first name is exposed
            assert " " not in c["first_name"]

        # 4. Out-of-scope passengers excluded:
        # Passenger on T-202 (Arjun) and passenger on future date (Kavita) must not appear
        candidate_names = [c["first_name"] for c in candidates]
        assert "Arjun" not in candidate_names
        assert "Kavita" not in candidate_names

        # 5. Group members excluded: Meera must not appear in Asha's match candidates
        assert "Meera" not in candidate_names


@pytest.mark.asyncio
async def test_protected_berth_rule_for_meera():
    """Verify Meera (age 62, LOWER berth) is never offered UPPER or MIDDLE berths."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Authenticate as Meera (PNR1000002)
        send_res = await client.post("/api/otp/send", json={"pnr": "PNR1000002"})
        code = send_res.json()["demo_otp"]
        verify_res = await client.post("/api/otp/verify", json={"pnr": "PNR1000002", "code": code})
        token = verify_res.json()["session_token"]

        match_res = await client.get("/api/match", headers={"X-Session-Token": token})
        assert match_res.status_code == 200
        data = match_res.json()

        # All candidates returned to Meera must offer LOWER berth (never worse)
        for cand in data["candidates"]:
            assert cand["berth_type"] == "LOWER", (
                f"Candidate {cand['first_name']} has berth type {cand['berth_type']}, "
                f"which violates protected berth rule for senior citizen Meera."
            )


@pytest.mark.asyncio
async def test_request_creation_and_quota_limits():
    """Verify request limits: 4th request -> 429, repeat target -> 409, and remaining quota."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Authenticate as Asha (PNR1000001)
        send_res = await client.post("/api/otp/send", json={"pnr": "PNR1000001"})
        code = send_res.json()["demo_otp"]
        verify_res = await client.post("/api/otp/verify", json={"pnr": "PNR1000001", "code": code})
        token = verify_res.json()["session_token"]
        headers = {"X-Session-Token": token}

        # Check initial quota: 0 used, 3 remaining
        quota_res = await client.get("/api/requests/remaining", headers=headers)
        assert quota_res.status_code == 200
        assert quota_res.json()["used"] == 0
        assert quota_res.json()["remaining"] == 3

        # Get candidates
        matches = (await client.get("/api/match", headers=headers)).json()["candidates"]
        cand1 = matches[0]  # Kiran
        cand2 = matches[1]  # Ravi
        cand3 = matches[2]  # Vikram or another
        cand4 = matches[3]

        # 1. Request 1: to cand1 (Kiran) -> 201 Created
        req1_res = await client.post("/api/requests", json={"target_id": cand1["candidate_id"]}, headers=headers)
        assert req1_res.status_code == 201
        req1_data = req1_res.json()
        assert req1_data["status"] == "PENDING_CONSENT"
        assert req1_data["requester_name"] == "Asha Sharma"
        assert req1_data["target_berth_no"] == cand1["berth_no"]

        # 2. Repeat request to cand1 -> 409 Conflict with DUPLICATE_TARGET
        repeat_res = await client.post("/api/requests", json={"target_id": cand1["candidate_id"]}, headers=headers)
        assert repeat_res.status_code == 409
        assert repeat_res.json()["code"] == "DUPLICATE_TARGET"

        # Check quota: 1 used, 2 remaining
        q2 = await client.get("/api/requests/remaining", headers=headers)
        assert q2.json()["used"] == 1
        assert q2.json()["remaining"] == 2

        # 3. Request 2: to cand2 (Ravi) -> 201 Created
        req2_res = await client.post("/api/requests", json={"target_id": cand2["candidate_id"]}, headers=headers)
        assert req2_res.status_code == 201

        # 4. Request 3: to cand3 -> 201 Created
        req3_res = await client.post("/api/requests", json={"target_id": cand3["candidate_id"]}, headers=headers)
        assert req3_res.status_code == 201

        # Check quota: 3 used, 0 remaining
        q3 = await client.get("/api/requests/remaining", headers=headers)
        assert q3.json()["used"] == 3
        assert q3.json()["remaining"] == 0

        # 5. Request 4: to cand4 -> 429 RateLimitException with REQUEST_LIMIT_REACHED
        req4_res = await client.post("/api/requests", json={"target_id": cand4["candidate_id"]}, headers=headers)
        assert req4_res.status_code == 429
        assert req4_res.json()["code"] == "REQUEST_LIMIT_REACHED"

        # 6. Check /api/requests/mine returns all 3 sent requests
        mine_res = await client.get("/api/requests/mine", headers=headers)
        assert mine_res.status_code == 200
        mine_data = mine_res.json()
        assert len(mine_data) == 3


@pytest.mark.asyncio
async def test_cancelled_declined_requests_count_toward_limit():
    """Verify that cancelled, declined, or expired requests still count toward the 3-request limit."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Authenticate as Asha
        send_res = await client.post("/api/otp/send", json={"pnr": "PNR1000001"})
        token = (await client.post("/api/otp/verify", json={"pnr": "PNR1000001", "code": send_res.json()["demo_otp"]})).json()["session_token"]
        headers = {"X-Session-Token": token}

        # Simulate 3 requests in DB with different terminal statuses (DECLINED, CANCELLED, EXPIRED)
        async with AsyncSessionLocal() as session:
            asha = await session.scalar(select(Passenger).where(Passenger.pnr == "PNR1000001"))
            kiran = await session.scalar(select(Passenger).where(Passenger.pnr == "PNR1000003"))
            ravi = await session.scalar(select(Passenger).where(Passenger.pnr == "PNR1000004"))
            vikram = await session.scalar(select(Passenger).where(Passenger.pnr == "PNR1000005"))

            r1 = ExchangeRequest(
                requester_id=asha.id, target_id=kiran.id, status=RequestStatus.DECLINED.value,
                category="BEST", start_station="S1", expiry_station="S4"
            )
            r2 = ExchangeRequest(
                requester_id=asha.id, target_id=ravi.id, status=RequestStatus.CANCELLED.value,
                category="POSSIBLE", start_station="S1", expiry_station="S4"
            )
            r3 = ExchangeRequest(
                requester_id=asha.id, target_id=vikram.id, status=RequestStatus.EXPIRED.value,
                category="POSSIBLE", start_station="S1", expiry_station="S3"
            )
            session.add_all([r1, r2, r3])
            await session.commit()

        # Quota should reflect 3 used and 0 remaining
        quota_res = await client.get("/api/requests/remaining", headers=headers)
        assert quota_res.json()["used"] == 3
        assert quota_res.json()["remaining"] == 0

        # Attempting any new request is rejected with 429
        cands = (await client.get("/api/match", headers=headers)).json()["candidates"]
        cand_target = next(c for c in cands if c["candidate_id"] not in (kiran.id, ravi.id, vikram.id))
        res_blocked = await client.post("/api/requests", json={"target_id": cand_target["candidate_id"]}, headers=headers)
        assert res_blocked.status_code == 429
        assert res_blocked.json()["code"] == "REQUEST_LIMIT_REACHED"


@pytest.mark.asyncio
async def test_audit_logs_persisted():
    """Verify that state changes record AuditLog rows."""
    async with AsyncSessionLocal() as session:
        logs = (await session.scalars(select(AuditLog))).all()
        actions = {l.action for l in logs}
        assert "SYSTEM_INIT" in actions
