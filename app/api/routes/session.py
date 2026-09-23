from fastapi import APIRouter, Depends

from app.api.deps import get_runtime
from app.api.schemas import HistoryMessage, HistoryResponse
from app.graph.runtime import AgentRuntime

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=dict)
async def create_session(runtime: AgentRuntime = Depends(get_runtime)) -> dict:
    return {"thread_id": runtime.new_thread_id()}


@router.get("/{thread_id}/history", response_model=HistoryResponse)
async def history(
    thread_id: str,
    runtime: AgentRuntime = Depends(get_runtime),
) -> HistoryResponse:
    messages = await runtime.history(thread_id)
    return HistoryResponse(
        thread_id=thread_id,
        messages=[HistoryMessage(**message) for message in messages],
    )
