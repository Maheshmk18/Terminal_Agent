import asyncio
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.core.logging import get_logger
from app.execution.sandbox import build_env, shell_command

logger = get_logger(__name__)

TRUNCATION_NOTICE = "\n... output truncated ..."


@dataclass(frozen=True)
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def as_text(self) -> str:
        if self.timed_out:
            return f"Command timed out.\n\n{self.stdout}".strip()

        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"stderr:\n{self.stderr}")
        if not parts:
            parts.append(f"(no output, exit code {self.exit_code})")

        return "\n\n".join(parts).strip()


async def run_command(command: str, cwd: Path | None = None) -> CommandResult:
    settings = get_settings()
    workdir = cwd or settings.working_dir

    logger.info("running_command", command=command, cwd=str(workdir))

    process = await asyncio.create_subprocess_exec(
        *shell_command(command),
        cwd=str(workdir),
        env=build_env(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=settings.command_timeout_seconds,
        )
    except TimeoutError:
        await _terminate(process)
        logger.warning("command_timed_out", command=command)
        return CommandResult(
            command=command,
            exit_code=-1,
            stdout="",
            stderr=f"Timed out after {settings.command_timeout_seconds}s",
            timed_out=True,
        )

    limit = settings.max_output_chars
    return CommandResult(
        command=command,
        exit_code=process.returncode or 0,
        stdout=_truncate(_decode(stdout), limit),
        stderr=_truncate(_decode(stderr), limit),
    )


async def _terminate(process: asyncio.subprocess.Process) -> None:
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except TimeoutError:
        process.kill()
        await process.wait()


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace").strip()


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + TRUNCATION_NOTICE
