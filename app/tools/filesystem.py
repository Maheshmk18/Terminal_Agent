from langchain_core.tools import tool

from app.config import get_settings
from app.core.exceptions import ToolExecutionError
from app.execution.sandbox import resolve_within

MAX_READ_CHARS = 20_000


@tool
def read_file(path: str) -> str:
    """Read a text file and return its contents.

    The path must be inside the working directory.
    """
    target = _resolve(path)

    if not target.is_file():
        return f"No such file: {path}"

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise ToolExecutionError(f"Could not read {path}: {error}") from error

    if len(content) > MAX_READ_CHARS:
        return content[:MAX_READ_CHARS] + "\n... file truncated ..."
    return content or "(file is empty)"


@tool
def write_file(path: str, content: str) -> str:
    """Write text to a file, creating parent directories and overwriting any existing file."""
    target = _resolve(path)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as error:
        raise ToolExecutionError(f"Could not write {path}: {error}") from error

    return f"Wrote {len(content)} characters to {path}"


@tool
def list_directory(path: str = ".") -> str:
    """List the files and folders in a directory."""
    target = _resolve(path)

    if not target.is_dir():
        return f"Not a directory: {path}"

    entries = sorted(target.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
    if not entries:
        return "(empty directory)"

    return "\n".join(_describe(entry) for entry in entries)


def _resolve(path: str):
    return resolve_within(get_settings().working_dir, path)


def _describe(entry) -> str:
    if entry.is_dir():
        return f"{entry.name}/"
    size = entry.stat().st_size
    return f"{entry.name}  ({size:,} bytes)"
