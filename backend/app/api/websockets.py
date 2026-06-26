"""
WebSocket broadcasting.

ConnectionManager tracks subscribers per run_id and pushes JSON-encoded
SimulationStepUpdate payloads to all of them. This is exercised fully by
the live dashboard in Phase 8, but it's built now and proven against the
Phase 2 fake stepper so the real-time plumbing is verified end-to-end
before Mesa (Phase 3) or React (Phase 7) exist.
"""
from collections import defaultdict
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, run_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[run_id].add(websocket)

    def disconnect(self, run_id: str, websocket: WebSocket) -> None:
        self._connections[run_id].discard(websocket)

    async def broadcast(self, run_id: str, message: str) -> None:
        dead = []
        for ws in self._connections[run_id]:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(run_id, ws)


manager = ConnectionManager()


@router.websocket("/ws/simulation/{run_id}")
async def simulation_updates(websocket: WebSocket, run_id: str) -> None:
    await manager.connect(run_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # keepalive ping from client; ignored
    except WebSocketDisconnect:
        manager.disconnect(run_id, websocket)
