"""WebSocket connection manager and event broadcasting."""

import json
from typing import Any, Dict, Optional, Set
from fastapi import WebSocket


class ConnectionManager:
    """In-memory WebSocket connection manager for real-time event broadcasting."""

    def __init__(self):
        # passenger_id -> set of websockets
        self._passenger_connections: Dict[int, Set[WebSocket]] = {}
        # TTE connections
        self._tte_connections: Set[WebSocket] = set()

    async def connect_passenger(self, ws: WebSocket, passenger_id: int) -> None:
        await ws.accept()
        if passenger_id not in self._passenger_connections:
            self._passenger_connections[passenger_id] = set()
        self._passenger_connections[passenger_id].add(ws)

    async def connect_tte(self, ws: WebSocket) -> None:
        await ws.accept()
        self._tte_connections.add(ws)

    def disconnect_passenger(self, ws: WebSocket, passenger_id: int) -> None:
        conns = self._passenger_connections.get(passenger_id)
        if conns:
            conns.discard(ws)
            if not conns:
                del self._passenger_connections[passenger_id]

    def disconnect_tte(self, ws: WebSocket) -> None:
        self._tte_connections.discard(ws)

    async def send_to_passenger(self, passenger_id: int, event: Dict[str, Any]) -> None:
        conns = self._passenger_connections.get(passenger_id, set())
        dead = []
        for ws in conns:
            try:
                await ws.send_text(json.dumps(event))
            except Exception:
                dead.append(ws)
        for ws in dead:
            conns.discard(ws)

    async def send_to_tte(self, event: Dict[str, Any]) -> None:
        dead = []
        for ws in self._tte_connections:
            try:
                await ws.send_text(json.dumps(event))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._tte_connections.discard(ws)

    async def broadcast_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        passenger_ids: Optional[list[int]] = None,
        include_tte: bool = False,
    ) -> None:
        """Broadcast an event to specified passengers and/or TTE."""
        event = {"type": event_type, "data": data}
        if passenger_ids:
            for pid in passenger_ids:
                await self.send_to_passenger(pid, event)
        if include_tte:
            await self.send_to_tte(event)


# Singleton instance
manager = ConnectionManager()
