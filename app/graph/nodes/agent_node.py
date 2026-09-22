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
            return {
                "messages": [
                    AIMessage(content=f"Stopping after {limit} steps without finishing the task.")
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
