from app.core.logging import get_logger
from app.graph.state import AgentState
from app.safety.classifier import classify_tool_call
from app.safety.models import PendingCall

logger = get_logger(__name__)


def safety_node(state: AgentState) -> dict:
    last = state["messages"][-1]
    tool_calls = getattr(last, "tool_calls", None) or []

    pending = [
        PendingCall(
            call_id=call["id"],
            tool_name=call["name"],
            arguments=call.get("args", {}),
            verdict=classify_tool_call(call["name"], call.get("args", {})),
        )
        for call in tool_calls
    ]

    for call in pending:
        logger.info(
            "classified_call",
            tool=call.tool_name,
            risk=call.verdict.risk.value,
            reason=call.verdict.reason,
        )

    return {"pending_calls": pending, "approved_ids": []}
