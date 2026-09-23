from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.graph.runtime import AgentRuntime

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws/{thread_id}")
async def agent_socket(websocket: WebSocket, thread_id: str) -> None:
    await websocket.accept()

    runtime: AgentRuntime | None = getattr(websocket.app.state, "runtime", None)
    if runtime is None:
        await websocket.send_json({"type": "error", "message": "Agent is not configured"})
        await websocket.close()
        return

    logger.info("socket_connected", thread_id=thread_id)

    try:
        while True:
            frame = await websocket.receive_json()
            await _handle(websocket, runtime, thread_id, frame)
    except WebSocketDisconnect:
        logger.info("socket_disconnected", thread_id=thread_id)
    except Exception as error:
        logger.exception("socket_failed", thread_id=thread_id)
        await _send_error(websocket, str(error))


async def _handle(websocket: WebSocket, runtime: AgentRuntime, thread_id: str, frame: dict) -> None:
    kind = frame.get("type")

    if kind == "message":
        stream = runtime.stream(thread_id, frame.get("text", ""))
    elif kind == "approval":
        decision = {"approved": bool(frame.get("approved"))}
        if ids := frame.get("approved_ids"):
            decision["approved_ids"] = ids
        stream = runtime.stream_resume(thread_id, decision)
    else:
        await _send_error(websocket, f"Unknown frame type: {kind}")
        return

    try:
        async for chunk in stream:
            await websocket.send_json(chunk)
    except Exception as error:
        logger.exception("stream_failed", thread_id=thread_id)
        await _send_error(websocket, str(error))


async def _send_error(websocket: WebSocket, message: str) -> None:
    with suppress(RuntimeError):
        await websocket.send_json({"type": "error", "message": message})
