import json
import logging
from typing import Any, Dict, List

from fastapi import WebSocket


class WebSocketConnectionManager:
    _instance = None

    # Overriding __new__ enforces the Singleton pattern
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Initialize state variables here so they only run once
            cls._instance._active_connections = {}
        return cls._instance
    
    @property
    def active_connections(self) -> Dict[str, WebSocket]:
        return self._active_connections

    async def connect(self, user_id: str, websocket: WebSocket):
        logging.info(f"Establishing a websocket connection with user {user_id}")
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logging.info(f"Websocket connection established successfully")

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_private_message(self, message: Dict[str, Any], target_user_id: str) -> bool:
        websocket = self.active_connections.get(target_user_id)
        if websocket:
            logging.info(f"Sending message {message} to {target_user_id}")
            await websocket.send_text(json.dumps(message))
            return True
        
        logging.error(f"Failed to send message to {target_user_id} because no websocket instance was found")
        return False