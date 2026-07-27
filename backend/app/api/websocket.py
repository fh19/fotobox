"""The one-directional status WebSocket (server -> client)."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.broadcaster import Broadcaster

router = APIRouter()


@router.websocket("/ws")
async def status_socket(websocket: WebSocket) -> None:
    broadcaster: Broadcaster = websocket.app.state.broadcaster
    await broadcaster.connect(websocket)
    try:
        # The client sends nothing but ping frames; we only read to notice hangups.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)
    except Exception:
        broadcaster.disconnect(websocket)
