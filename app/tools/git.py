from langchain_core.tools import tool

from app.execution.runner import run_command


@tool
async def git_status() -> str:
    """Show the current git branch and which files have changed."""
    result = await run_command("git status --short --branch")
    return result.as_text()


@tool
async def git_diff(staged: bool = False) -> str:
    """Show the diff of uncommitted changes. Set staged to true for changes already staged."""
    command = "git diff --staged" if staged else "git diff"
    result = await run_command(command)
    return result.as_text() or "(no changes)"


@tool
async def git_log(limit: int = 10) -> str:
    """Show recent commits, newest first."""
    count = max(1, min(limit, 50))
    result = await run_command(f"git log --oneline -{count}")
    return result.as_text()
