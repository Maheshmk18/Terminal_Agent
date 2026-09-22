from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.graph.edges import route_after_agent, route_after_safety
from app.graph.nodes.agent_node import build_agent_node
from app.graph.nodes.approval_node import approval_node
from app.graph.nodes.safety_node import safety_node
from app.graph.nodes.tool_node import tool_node
from app.graph.state import AgentState
from app.llm.factory import build_llm


def build_graph(llm: BaseChatModel | None = None, checkpointer=None):
    builder = StateGraph(AgentState)

    builder.add_node("agent", build_agent_node(llm or build_llm()))
    builder.add_node("safety", safety_node)
    builder.add_node("approval", approval_node)
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", route_after_agent, {"safety": "safety", END: END})
    builder.add_conditional_edges(
        "safety",
        route_after_safety,
        {"approval": "approval", "tools": "tools"},
    )
    builder.add_edge("approval", "tools")
    builder.add_edge("tools", "agent")

    return builder.compile(checkpointer=checkpointer or MemorySaver())
