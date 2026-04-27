from fastapi import WebSocket
from typing import Dict, List

class ConnectionManager:
    def __init__(self):
        # Maps a consultation_id (UUID string) to a list of active WebSocket connections.
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, consultation_id: str):
        await websocket.accept()
        if consultation_id not in self.active_connections:
            self.active_connections[consultation_id] = []
        self.active_connections[consultation_id].append(websocket)

    def disconnect(self, websocket: WebSocket, consultation_id: str):
        if consultation_id in self.active_connections:
            self.active_connections[consultation_id].remove(websocket)
            # Cleanup memory if no one is looking at this consultation anymore
            if not self.active_connections[consultation_id]:
                del self.active_connections[consultation_id] 

    async def broadcast(self, consultation_id: str, message: dict):
        """Pushes a JSON message to anyone looking at this specific consultation."""
        if consultation_id in self.active_connections:
            for connection in self.active_connections[consultation_id]:
                await connection.send_json(message)

# Create a global instance to use across your API
ws_manager = ConnectionManager()