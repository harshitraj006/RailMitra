"""Integration tests for family group seat exchange requests."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

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
async def test_group_request_creation_and_status():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Rajesh Verma (PNR: PNR1000010, id: 8) in Verma family
        # Let's inspect who Rajesh's candidates are
        rajesh_token = await get_token_for_pnr(client, "PNR1000010")

        match_res = await client.get("/api/match", headers={"X-Session-Token": rajesh_token})
        assert match_res.status_code == 200
        candidates = match_res.json()["candidates"]
        assert len(candidates) > 0
        target_1 = candidates[0]["candidate_id"]

        # Sunita Verma (PNR: PNR1000011) in Verma family
        sunita_token = await get_token_for_pnr(client, "PNR1000011")
        sunita_matches = await client.get("/api/match", headers={"X-Session-Token": sunita_token})
        s_candidates = sunita_matches.json()["candidates"]
        target_2 = next(c["candidate_id"] for c in s_candidates if c["candidate_id"] != target_1)

        # Get Rajesh's and Sunita's passenger IDs
        rajesh_prof = (await client.get("/api/me", headers={"X-Session-Token": rajesh_token})).json()
        sunita_prof = (await client.get("/api/me", headers={"X-Session-Token": sunita_token})).json()

        payload = {
            "desired_seating": [
                {"member_id": rajesh_prof["id"], "target_id": target_1},
                {"member_id": sunita_prof["id"], "target_id": target_2},
            ]
        }
        create_res = await client.post(
            "/api/group-requests",
            headers={"X-Session-Token": rajesh_token},
            json=payload,
        )
        assert create_res.status_code == 201
        group_data = create_res.json()
        assert group_data["total_swaps"] == 2
        assert group_data["confirmed_swaps"] == 0
        assert group_data["status"] == "PENDING"
        assert group_data["is_fully_confirmed"] is False
        group_req_id = group_data["group_request_id"]

        # Fetch group request by id
        fetch_res = await client.get(
            f"/api/group-requests/{group_req_id}",
            headers={"X-Session-Token": rajesh_token},
        )
        assert fetch_res.status_code == 200
        assert fetch_res.json()["group_request_id"] == group_req_id


@pytest.mark.asyncio
async def test_group_request_limit_violation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Asha is not in a group (wait, Asha is in Asha's family, but Vikram is not in any group)
        vikram_token = await get_token_for_pnr(client, "PNR1000005")
        bad_res = await client.post(
            "/api/group-requests",
            headers={"X-Session-Token": vikram_token},
            json={"desired_seating": [{"member_id": 5, "target_id": 3}]},
        )
        assert bad_res.status_code == 400
        assert bad_res.json()["code"] == "NOT_IN_GROUP"
