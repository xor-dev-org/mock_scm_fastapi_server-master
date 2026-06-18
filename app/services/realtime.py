import os
from collections import defaultdict
from typing import Dict, List, Set

from fastapi import WebSocket


class RealtimeGateway:
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self.signalr_endpoint = os.getenv("AZURE_SIGNALR_ENDPOINT", "")
        self.signalr_hub = os.getenv("AZURE_SIGNALR_HUB", "procurementchat")
        self.signalr_access_key = os.getenv("AZURE_SIGNALR_ACCESS_KEY", "")

    @property
    def signalr_enabled(self) -> bool:
        return bool(self.signalr_endpoint and self.signalr_hub and self.signalr_access_key)

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[user_id].add(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        if user_id not in self._connections:
            return

        if websocket in self._connections[user_id]:
            self._connections[user_id].remove(websocket)

        if not self._connections[user_id]:
            self._connections.pop(user_id, None)

    async def notify_user(self, user_id: str, payload: Dict) -> None:
        stale = []
        sockets = self._connections.get(user_id, set())

        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self.disconnect(user_id, ws)

    async def notify_users(self, user_ids: List[str], payload: Dict) -> None:
        for user_id in set(user_ids):
            await self.notify_user(user_id, payload)


realtime_gateway = RealtimeGateway()
