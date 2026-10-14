"""Tests for WebSocket real-time event broadcasting."""

import pytest
from starlette.testclient import TestClient
from app.main import app
from app.config import settings
from app.ws.manager import manager


def test_websocket_tte_connection():
    client = TestClient(app)
    with client.websocket_connect(f"/ws?role=tte&tte_key={settings.TTE_KEY}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "connected"
        assert msg["role"] == "tte"
        # Test heartbeat
        ws.send_text("ping")
        resp = ws.receive_text()
        assert resp == "pong"


def test_websocket_passenger_connection():
    client = TestClient(app)
    # Connect with Asha's PNR
    with client.websocket_connect("/ws?token=PNR1000001") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "connected"
        assert msg["passenger_id"] == 1


def test_websocket_invalid_auth():
    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws?token=INVALID_PNR_TOKEN"):
            pass
