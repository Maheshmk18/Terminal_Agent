from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from app.config import get_settings
from app.graph.interrupts import get_pending_interrupt

NODES_PER_TURN = 3
RECURSION_HEADROOM = 10

STUCK_MESSAGE = (
    "I could not finish this in the steps available. "
    "Try a narrower request, or raise MAX_ITERATIONS in .env."
)


class AgentRuntime:
    def __init__(self, graph) -> None:
        self._graph = graph

    @staticmethod
    def new_thread_id() -> str:
        return uuid4().hex[:12]

    async def send(self, thread_id: str, message: str) -> dict:
        payload = {"messages": [HumanMessage(content=message)], "iterations": 0}
        return await self._run(thread_id, payload)

    async def resume(self, thread_id: str, decision: dict) -> dict:
        return await self._run(thread_id, Command(resume=decision))

    async def history(self, thread_id: str) -> list[dict]:
        snapshot = await self._graph.aget_state(self._config(thread_id))
        messages = snapshot.values.get("messages", []) if snapshot.values else []
        return [
            {"role": message.type, "content": str(message.content)}
            for message in messages
            if str(message.content).strip()
        ]

    async def stream(self, thread_id: str, message: str):
        payload = {"messages": [HumanMessage(content=message)], "iterations": 0}
        async for chunk in self._stream(thread_id, payload):
            yield chunk

    async def stream_resume(self, thread_id: str, decision: dict):
        async for chunk in self._stream(thread_id, Command(resume=decision)):
            yield chunk

    async def _run(self, thread_id: str, payload) -> dict:
        config = self._config(thread_id)

        try:
            result = await self._graph.ainvoke(payload, config)
        except GraphRecursionError:
            return {
                "thread_id": thread_id,
                "reply": STUCK_MESSAGE,
                "awaiting_approval": False,
                "approval_request": None,
            }

        interrupt = await get_pending_interrupt(self._graph, config)

        return {
            "thread_id": thread_id,
            "reply": self._last_text(result),
            "awaiting_approval": interrupt is not None,
            "approval_request": interrupt,
        }

    async def _stream(self, thread_id: str, payload):
        config = self._config(thread_id)

        try:
            async for event in self._graph.astream_events(payload, config, version="v2"):
                if token := self._token_from(event):
                    yield {"type": "token", "text": token}
        except GraphRecursionError:
            yield {"type": "done", "reply": STUCK_MESSAGE}
            return

        interrupt = await get_pending_interrupt(self._graph, config)
        if interrupt:
            yield interrupt
            return

        snapshot = await self._graph.aget_state(config)
        yield {"type": "done", "reply": self._last_text(snapshot.values)}

    @staticmethod
    def _token_from(event: dict) -> str:
        if event.get("event") != "on_chat_model_stream":
            return ""
        chunk = event.get("data", {}).get("chunk")
        return str(getattr(chunk, "content", "") or "")

    @staticmethod
    def _last_text(values: dict) -> str:
        for message in reversed(values.get("messages", [])):
            if message.type == "ai" and str(message.content).strip():
                return str(message.content)
        return ""

    @staticmethod
    def _config(thread_id: str) -> dict:
        limit = get_settings().max_iterations
        return {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": limit * NODES_PER_TURN + RECURSION_HEADROOM,
        }
