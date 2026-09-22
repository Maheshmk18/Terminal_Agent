from langchain_core.messages import ToolMessage

from app.core.exceptions import ToolExecutionError
from app.core.logging import get_logger
from app.graph.state import AgentState
from app.safety.models import RiskLevel
from app.tools.registry import get_tool

logger = get_logger(__name__)


async def tool_node(state: AgentState) -> dict:
    pending = state.get("pending_calls", [])
    approved = set(state.get("approved_ids", []))

    messages = []
    for call in pending:
        content = await _resolve(call, approved)
        messages.append(ToolMessage(content=content, tool_call_id=call.call_id))

    return {"messages": messages, "pending_calls": [], "approved_ids": []}


async def _resolve(call, approved: set[str]) -> str:
    if call.verdict.risk is RiskLevel.BLOCKED:
        logger.warning("blocked_call", tool=call.tool_name, reason=call.verdict.reason)
        return f"Blocked: {call.verdict.reason}. Suggest a safer approach."

    if call.call_id not in approved:
        logger.info("call_denied", tool=call.tool_name)
        return "The user denied this command. Ask what they would prefer instead."

    return await _execute(call)


async def _execute(call) -> str:
    tool = get_tool(call.tool_name)
    if tool is None:
        return f"Unknown tool: {call.tool_name}"

    try:
        return str(await tool.ainvoke(call.arguments))
    except ToolExecutionError as error:
        logger.warning("tool_failed", tool=call.tool_name, error=str(error))
        return f"Tool error: {error}"
    except Exception as error:
        logger.exception("tool_crashed", tool=call.tool_name)
        return f"Tool crashed: {type(error).__name__}: {error}"
