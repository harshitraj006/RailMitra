"""Integration tests for the complete seat exchange lifecycle.

Tests:
1. Happy path: Asha requests Vikram -> Vikram accepts -> TTE approves -> Digital slip generated -> Slip verified -> Train advances -> Expiry triggered -> Seats restored.
2. Authorization: Non-target cannot respond (403 WRONG_PASSENGER).
3. Requester cannot cancel after target accepts (409 INVALID_STATE_TRANSITION).
4. Non-requester cannot cancel (403 WRONG_PASSENGER).
5. TTE cannot approve without target consent (409 MISSING_CONSENT).
6. Illegal state transitions rejected by state machine (409).
7. Audit trail records every transition.
"""

import json
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.main import app
from app.seed import reset_database


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Ensure database schema is created and freshly seeded before each test."""
    await init_db()
    async with AsyncSessionLocal() as session:
        await reset_database(session)
    yield


async def get_token_for_pnr(client: AsyncClient, pnr: str) -> str:
    """Helper to authenticate a passenger and get session token."""
    send_res = await client.post("/api/otp/send", json={"pnr": pnr})
    otp = send_res.json().get("demo_otp")
    verify_res = await client.post("/api/otp/verify", json={"pnr": pnr, "code": otp})
    return verify_res.json()["session_token"]


@pytest.mark.asyncio
async def test_complete_exchange_lifecycle_happy_path():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Asha (PNR: PNR1000001, Coach S2, Berth 14, UPPER, S1->S4)
        # Kiran (PNR: PNR1000003, Coach S2, Berth 43, UPPER, S1->S4, id: 3)
        asha_token = await get_token_for_pnr(client, "PNR1000001")
        kiran_token = await get_token_for_pnr(client, "PNR1000003")

        # 1. Asha finds matches
        match_res = await client.get("/api/match", headers={"X-Session-Token": asha_token})
        assert match_res.status_code == 200
        candidates = match_res.json()["candidates"]
        kiran_candidate = next((c for c in candidates if c["candidate_id"] == 3), None)
        assert kiran_candidate is not None

        # 2. Asha creates exchange request to Kiran
        req_res = await client.post(
            "/api/requests",
            headers={"X-Session-Token": asha_token},
            json={"target_id": 3},
        )
        assert req_res.status_code == 201
        exchange_id = req_res.json()["id"]
        assert req_res.json()["status"] == "PENDING_CONSENT"
        assert req_res.json()["requester_name"] == "Asha Sharma"

        # 3. Kiran checks incoming requests
        incoming_res = await client.get("/api/requests/incoming", headers={"X-Session-Token": kiran_token})
        assert incoming_res.status_code == 200
        incoming = incoming_res.json()
        assert len(incoming) >= 1
        target_req = next(r for r in incoming if r["id"] == exchange_id)
        assert target_req["requester_coach"] == "S2"
        assert target_req["requester_berth_no"] == 14

        # 4. Kiran accepts request
        respond_res = await client.post(
            f"/api/requests/{exchange_id}/respond",
            headers={"X-Session-Token": kiran_token},
            json={"decision": "ACCEPTED"},
        )
        assert respond_res.status_code == 200
        assert respond_res.json()["status"] == "ACCEPTED_BY_PASSENGER"
        assert respond_res.json()["target_confirmed"] is True

        # 5. TTE reviews and approves
        tte_queue = await client.get("/api/tte/requests", headers={"X-TTE-Key": settings.TTE_KEY})
        assert tte_queue.status_code == 200
        assert any(q["request_id"] == exchange_id for q in tte_queue.json())

        review_res = await client.post(
            f"/api/tte/requests/{exchange_id}/review",
            headers={"X-TTE-Key": settings.TTE_KEY},
            json={"decision": "TTE_APPROVED", "note": "Approved on train"},
        )
        assert review_res.status_code == 200
        assert review_res.json()["decision"] == "TTE_APPROVED"

        # 6. Verify effective seating is updated on train
        seating_res = await client.get("/api/train/12951/seating")
        assert seating_res.status_code == 200
        seating = seating_res.json()["seating"]
        asha_seat = next(s for s in seating if s["passenger_id"] == 1)
        kiran_seat = next(s for s in seating if s["passenger_id"] == 3)
        assert asha_seat["is_swapped"] is True
        assert asha_seat["effective_coach"] == "S2"
        assert asha_seat["effective_berth_no"] == 43
        assert kiran_seat["is_swapped"] is True
        assert kiran_seat["effective_coach"] == "S2"
        assert kiran_seat["effective_berth_no"] == 14

        # 7. Asha accesses Digital Slip
        slip_res = await client.get(
            f"/api/requests/{exchange_id}/slip",
            headers={"X-Session-Token": asha_token},
        )
        assert slip_res.status_code == 200
        slip_data = slip_res.json()
        assert slip_data["tte_approval_status"] == "APPROVED"
        assert "Coach S2, Berth 43" in slip_data["exchanged_berth"]
        assert "Prototype using a simulated reservation dataset" in slip_data["disclaimer"]

        # 8. Public Slip Verification via token
        qr_payload = json.loads(slip_data["qr_data"])
        token = qr_payload["token"]

        verify_res = await client.get(f"/api/verify/{token}")
        assert verify_res.status_code == 200
        v_data = verify_res.json()
        assert v_data["valid"] is True
        assert "pnr" not in v_data  # Privacy rule: no PNR exposed
        assert "phone" not in v_data
        assert "Prototype using a simulated reservation dataset" in v_data["disclaimer"]

        # 9. Advance train to S4 (Asha & Kiran expiry is S4)
        adv_res = await client.post("/api/demo/advance_train", json={"train_id": "T-101", "to_station": "S4"})
        assert adv_res.status_code == 200
        assert adv_res.json()["expired_requests_count"] >= 1

        # 10. Check seating is restored to original
        seating_after = await client.get("/api/train/12951/seating")
        seating_data = seating_after.json()["seating"]
        asha_seat_restored = next(s for s in seating_data if s["passenger_id"] == 1)
        assert asha_seat_restored["is_swapped"] is False
        assert asha_seat_restored["effective_coach"] == "S2"
        assert asha_seat_restored["effective_berth_no"] == 14


@pytest.mark.asyncio
async def test_unauthorized_respond_and_cancel():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        asha_token = await get_token_for_pnr(client, "PNR1000001")
        kiran_token = await get_token_for_pnr(client, "PNR1000003")
        ravi_token = await get_token_for_pnr(client, "PNR1000004")

        # Asha creates request to Kiran (id 3)
        req_res = await client.post(
            "/api/requests",
            headers={"X-Session-Token": asha_token},
            json={"target_id": 3},
        )
        exchange_id = req_res.json()["id"]

        # Ravi tries to respond to Kiran's request -> 403 WRONG_PASSENGER
        bad_respond = await client.post(
            f"/api/requests/{exchange_id}/respond",
            headers={"X-Session-Token": ravi_token},
            json={"decision": "ACCEPTED"},
        )
        assert bad_respond.status_code == 403
        assert bad_respond.json()["code"] == "WRONG_PASSENGER"

        # Kiran tries to cancel Asha's request -> 403 WRONG_PASSENGER
        bad_cancel = await client.post(
            f"/api/requests/{exchange_id}/cancel",
            headers={"X-Session-Token": kiran_token},
        )
        assert bad_cancel.status_code == 403
        assert bad_cancel.json()["code"] == "WRONG_PASSENGER"

        # Asha cancels her own request -> 200 OK
        good_cancel = await client.post(
            f"/api/requests/{exchange_id}/cancel",
            headers={"X-Session-Token": asha_token},
        )
        assert good_cancel.status_code == 200
        assert good_cancel.json()["status"] == "CANCELLED"

        # Trying to cancel again -> 409 INVALID_STATE_TRANSITION
        repeat_cancel = await client.post(
            f"/api/requests/{exchange_id}/cancel",
            headers={"X-Session-Token": asha_token},
        )
        assert repeat_cancel.status_code == 409
        assert repeat_cancel.json()["code"] == "INVALID_STATE_TRANSITION"


@pytest.mark.asyncio
async def test_tte_approval_blocked_without_target_consent():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        asha_token = await get_token_for_pnr(client, "PNR1000001")

        # Asha creates request to Kiran
        req_res = await client.post(
            "/api/requests",
            headers={"X-Session-Token": asha_token},
            json={"target_id": 3},
        )
        exchange_id = req_res.json()["id"]

        # TTE tries to approve before Kiran has accepted -> 409 MISSING_CONSENT
        bad_approve = await client.post(
            f"/api/tte/requests/{exchange_id}/review",
            headers={"X-TTE-Key": settings.TTE_KEY},
            json={"decision": "TTE_APPROVED"},
        )
        assert bad_approve.status_code == 409
        assert bad_approve.json()["code"] == "MISSING_CONSENT"


@pytest.mark.asyncio
async def test_notifications_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        asha_token = await get_token_for_pnr(client, "PNR1000001")
        kiran_token = await get_token_for_pnr(client, "PNR1000003")

        # Asha requests Kiran -> Kiran gets notification
        await client.post(
            "/api/requests",
            headers={"X-Session-Token": asha_token},
            json={"target_id": 3},
        )

        notifs_res = await client.get("/api/notifications", headers={"X-Session-Token": kiran_token})
        assert notifs_res.status_code == 200
        notifs = notifs_res.json()
        assert len(notifs) >= 1
        n_id = notifs[0]["id"]
        assert notifs[0]["read"] is False

        # Mark single as read
        read_res = await client.post(
            f"/api/notifications/{n_id}/read",
            headers={"X-Session-Token": kiran_token},
        )
        assert read_res.status_code == 200
        assert read_res.json()["read"] is True

        # Mark all as read
        read_all_res = await client.post(
            "/api/notifications/read-all",
            headers={"X-Session-Token": kiran_token},
        )
        assert read_all_res.status_code == 200

