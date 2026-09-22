from langgraph.graph import END

from app.graph.state import AgentState


def route_after_agent(state: AgentState) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "safety"
    return END


def route_after_safety(state: AgentState) -> str:
    pending = state.get("pending_calls", [])
    if any(call.verdict.risk.needs_approval for call in pending):
        return "approval"
    return "tools"
