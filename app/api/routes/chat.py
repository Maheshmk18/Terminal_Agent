from fastapi import APIRouter, Depends

from app.api.deps import get_runtime
from app.api.schemas import ApprovalDecision, ChatRequest, ChatResponse
from app.graph.runtime import AgentRuntime

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    runtime: AgentRuntime = Depends(get_runtime),
) -> ChatResponse:
    thread_id = request.thread_id or runtime.new_thread_id()
    result = await runtime.send(thread_id, request.message)
    return ChatResponse(**result)


@router.post("/approve", response_model=ChatResponse)
async def approve(
    decision: ApprovalDecision,
    runtime: AgentRuntime = Depends(get_runtime),
) -> ChatResponse:
    payload = {"approved": decision.approved}
    if decision.approved_ids is not None:
        payload["approved_ids"] = decision.approved_ids

    result = await runtime.resume(decision.thread_id, payload)
    return ChatResponse(**result)
