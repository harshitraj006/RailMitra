"""Integration tests for Train Ticket Examiner (TTE) dashboard APIs."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.main import app
from app.seed import reset_database


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    async with AsyncSessionLocal() as session:
        await reset_database(session)
    yield


async def get_token_for_pnr(client: AsyncClient, pnr: str) -> str:
    send_res = await client.post("/api/otp/send", json={"pnr": pnr})
    otp = send_res.json().get("demo_otp")
    verify_res = await client.post("/api/otp/verify", json={"pnr": pnr, "code": otp})
    return verify_res.json()["session_token"]


@pytest.mark.asyncio
async def test_tte_access_control():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Missing TTE key -> 403
        res_no_key = await client.get("/api/tte/requests")
        assert res_no_key.status_code == 403

        # Wrong TTE key -> 403
        res_wrong_key = await client.get("/api/tte/requests", headers={"X-TTE-Key": "wrong-key"})
        assert res_wrong_key.status_code == 403

        # Valid TTE key -> 200
        res_valid = await client.get("/api/tte/requests", headers={"X-TTE-Key": settings.TTE_KEY})
        assert res_valid.status_code == 200


@pytest.mark.asyncio
async def test_tte_review_actions_and_audit():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        asha_token = await get_token_for_pnr(client, "PNR1000001")
        kiran_token = await get_token_for_pnr(client, "PNR1000003")

        # Asha requests Kiran
        req_res = await client.post(
            "/api/requests",
            headers={"X-Session-Token": asha_token},
            json={"target_id": 3},
        )
        exchange_id = req_res.json()["id"]

        # Kiran accepts
        await client.post(
            f"/api/requests/{exchange_id}/respond",
            headers={"X-Session-Token": kiran_token},
            json={"decision": "ACCEPTED"},
        )

        # TTE requests clarification
        clarify_res = await client.post(
            f"/api/tte/requests/{exchange_id}/review",
            headers={"X-TTE-Key": settings.TTE_KEY},
            json={"decision": "CLARIFICATION_REQUESTED", "note": "Please verify age with ID proof"},
        )
        assert clarify_res.status_code == 200
        assert clarify_res.json()["decision"] == "CLARIFICATION_REQUESTED"

        # TTE can then approve after clarification
        approve_res = await client.post(
            f"/api/tte/requests/{exchange_id}/review",
            headers={"X-TTE-Key": settings.TTE_KEY},
            json={"decision": "TTE_APPROVED", "note": "ID verified. Exchange approved."},
        )
        assert approve_res.status_code == 200
        assert approve_res.json()["decision"] == "TTE_APPROVED"

        # Verify audit trail contains the actions
        audit_res = await client.get(
            f"/api/tte/audit?request_id={exchange_id}",
            headers={"X-TTE-Key": settings.TTE_KEY},
        )
        assert audit_res.status_code == 200
        logs = audit_res.json()
        actions = [l["action"] for l in logs]
        assert "CREATED" in actions
        assert "CONSENT_ACCEPTED" in actions
        assert "CLARIFICATION_REQUESTED" in actions
        assert "TTE_APPROVED" in actions

        # TTE train summary
        summary_res = await client.get(
            "/api/tte/train/T-101/summary",
            headers={"X-TTE-Key": settings.TTE_KEY},
        )
        assert summary_res.status_code == 200
        assert summary_res.json()["active_exchanges"] == 2  # 2 passengers involved
