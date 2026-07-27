"""WebSocket fan-out.

The WebSocket is one-directional (server -> client, api-contract). The broadcaster
keeps the set of connected clients and pushes each message to all of them,
dropping any that have gone away.
"""

from __future__ import annotations

from starlette.websockets import WebSocket, WebSocketState


class Broadcaster:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        dead: list[WebSocket] = []
        for websocket in list(self._connections):
            if websocket.application_state != WebSocketState.CONNECTED:
                dead.append(websocket)
                continue
            try:
                await websocket.send_json(message)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self._connections.discard(websocket)

    @property
    def count(self) -> int:
        return len(self._connections)
