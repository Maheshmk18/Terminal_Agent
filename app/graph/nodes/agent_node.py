from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage

from app.config import get_settings
from app.core.logging import get_logger
from app.graph.state import AgentState
from app.llm.prompts import build_system_prompt
from app.tools.registry import ALL_TOOLS

logger = get_logger(__name__)


def build_agent_node(llm: BaseChatModel):
    model = llm.bind_tools(ALL_TOOLS)

    async def agent_node(state: AgentState) -> dict:
        iterations = state.get("iterations", 0)
        limit = get_settings().max_iterations

        if iterations >= limit:
            logger.warning("iteration_limit_reached", limit=limit)
            summary = _summarise_progress(state["messages"])
            return {
                "messages": [
                    AIMessage(
                        content=(
                            f"I stopped after {limit} steps without finishing.\n\n{summary}\n\n"
                            "Try narrowing the request, or raise MAX_ITERATIONS in .env."
                        )
                    )
                ],
                "pending_calls": [],
            }

        working_dir = state.get("working_dir") or str(get_settings().working_dir)
        prompt = SystemMessage(content=build_system_prompt(working_dir))
        response = await model.ainvoke([prompt, *state["messages"]])

        logger.info("agent_replied", tool_calls=len(getattr(response, "tool_calls", []) or []))

        return {
            "messages": [response],
            "iterations": iterations + 1,
            "pending_calls": [],
        }

    return agent_node


def _summarise_progress(messages: list) -> str:
    commands = [
        call["args"]["command"]
        for message in messages
        for call in (getattr(message, "tool_calls", None) or [])
        if "command" in call.get("args", {})
    ]

    if not commands:
        return "No commands were run."

    listed = "\n".join(f"  {command}" for command in commands[-5:])
    return f"What I ran:\n{listed}"
