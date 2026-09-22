import json

import websockets


class AgentClient:
    def __init__(self, base_url: str, thread_id: str) -> None:
        self._url = f"{base_url.rstrip('/')}/ws/{thread_id}".replace("http", "ws", 1)
        self._socket = None

    async def __aenter__(self) -> "AgentClient":
        self._socket = await websockets.connect(self._url, max_size=8 * 1024 * 1024)
        return self

    async def __aexit__(self, *exc_info) -> None:
        if self._socket is not None:
            await self._socket.close()

    async def send_message(self, text: str):
        async for frame in self._exchange({"type": "message", "text": text}):
            yield frame

    async def send_approval(self, approved: bool):
        async for frame in self._exchange({"type": "approval", "approved": approved}):
            yield frame

    async def _exchange(self, frame: dict):
        await self._socket.send(json.dumps(frame))

        async for raw in self._socket:
            message = json.loads(raw)
            yield message

            if message.get("type") in {"done", "error", "approval_request"}:
                return
