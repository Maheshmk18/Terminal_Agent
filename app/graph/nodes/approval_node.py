from langgraph.types import interrupt

from app.core.logging import get_logger
from app.graph.state import AgentState

logger = get_logger(__name__)


def approval_node(state: AgentState) -> dict:
    pending = state.get("pending_calls", [])
    needing_approval = [call for call in pending if call.verdict.risk.needs_approval]

    if not needing_approval:
        return {"approved_ids": [call.call_id for call in pending]}

    request = {
        "type": "approval_request",
        "calls": [
            {
                "call_id": call.call_id,
                "tool": call.tool_name,
                "command": call.display,
                "risk": call.verdict.risk.value,
                "reason": call.verdict.reason,
            }
            for call in needing_approval
        ],
    }

    logger.info("awaiting_approval", count=len(needing_approval))
    decision = interrupt(request)

    approved = _approved_ids(decision, needing_approval)
    auto_approved = [
        call.call_id for call in pending if not call.verdict.risk.needs_approval
    ]

    logger.info("approval_received", approved=len(approved))
    return {"approved_ids": [*auto_approved, *approved]}


def _approved_ids(decision, needing_approval) -> list[str]:
    if isinstance(decision, bool):
        return [call.call_id for call in needing_approval] if decision else []

    if isinstance(decision, dict):
        if "approved_ids" in decision:
            return list(decision["approved_ids"])
        if decision.get("approved"):
            return [call.call_id for call in needing_approval]
        return []

    if isinstance(decision, list):
        return list(decision)

    return []
