import os
import platform
from pathlib import Path

from app.core.exceptions import ToolExecutionError

BLOCKED_ENV_PREFIXES = ("GROQ_", "OPENAI_", "ANTHROPIC_", "AWS_", "AZURE_")
BLOCKED_ENV_KEYWORDS = ("TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")

WIDE_BUFFER = (
    "try{$h=(Get-Host).UI.RawUI;$s=$h.BufferSize;$s.Width=500;$h.BufferSize=$s}catch{};"
)


def resolve_within(root: Path, target: str | Path) -> Path:
    root = root.resolve()
    candidate = Path(target).expanduser()
    resolved = candidate if candidate.is_absolute() else root / candidate
    resolved = resolved.resolve()

    if resolved != root and root not in resolved.parents:
        raise ToolExecutionError(f"Path escapes the working directory: {target}")

    return resolved


def build_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if not _is_secret(key)}


def shell_command(command: str) -> list[str]:
    if platform.system() == "Windows":
        return ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _widen(command)]
    return ["/bin/bash", "-c", command]


def _widen(command: str) -> str:
    return f"{WIDE_BUFFER}{command}"


def _is_secret(key: str) -> bool:
    upper = key.upper()
    if upper.startswith(BLOCKED_ENV_PREFIXES):
        return True
    return any(word in upper for word in BLOCKED_ENV_KEYWORDS)
