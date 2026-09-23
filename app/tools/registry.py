from langchain_core.tools import BaseTool

from app.tools.filesystem import list_directory, read_file, write_file
from app.tools.git import git_diff, git_log, git_status
from app.tools.shell import run_shell_command

ALL_TOOLS: list[BaseTool] = [
    run_shell_command,
    read_file,
    write_file,
    list_directory,
    git_status,
    git_diff,
    git_log,
]

TOOLS_BY_NAME: dict[str, BaseTool] = {tool.name: tool for tool in ALL_TOOLS}


def get_tool(name: str) -> BaseTool | None:
    return TOOLS_BY_NAME.get(name)
