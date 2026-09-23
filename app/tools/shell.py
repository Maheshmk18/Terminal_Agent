from langchain_core.tools import tool

from app.execution.runner import run_command


@tool
async def run_shell_command(command: str) -> str:
    """Run a shell command and return its output.

    Use this when no dedicated tool fits. Run one command per call.
    """
    result = await run_command(command)
    return result.as_text()
