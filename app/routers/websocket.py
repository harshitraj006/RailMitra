"""WebSocket endpoint for real-time updates."""

from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Passenger, Session
from app.ws.manager import manager

router = APIRouter(tags=["Realtime WebSockets"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    tte_key: Optional[str] = Query(None),
):
    """Real-time event streaming WebSocket endpoint.

    Connect with:
    - Passenger: /ws?token=<session_token>
    - TTE: /ws?role=tte&tte_key=<tte_key>
    """
    if role == "tte" or tte_key == settings.TTE_KEY:
        await manager.connect_tte(websocket)
        try:
            await websocket.send_json({"type": "connected", "role": "tte"})
            while True:
                data = await websocket.receive_text()
                # Echo / heartbeat ping-pong
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            manager.disconnect_tte(websocket)
        return

    # Authenticate passenger via token
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return

    passenger_id = None
    async with AsyncSessionLocal() as db:
        # Check by session token first
        stmt = select(Session).where(Session.token == token.strip())
        sess = (await db.execute(stmt)).scalar_one_or_none()
        if sess:
            passenger_id = sess.passenger_id
        else:
            # Fallback: check if token passed was passenger PNR directly (for easy demo testing)
            p_stmt = select(Passenger).where(Passenger.pnr == token.strip())
            p = (await db.execute(p_stmt)).scalar_one_or_none()
            if p:
                passenger_id = p.id

    if not passenger_id:
        await websocket.close(code=1008, reason="Invalid session token")
        return

    await manager.connect_passenger(websocket, passenger_id)
    try:
        await websocket.send_json({"type": "connected", "passenger_id": passenger_id})
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect_passenger(websocket, passenger_id)
