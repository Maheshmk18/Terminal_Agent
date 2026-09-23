import platform

import pytest

from app.execution.runner import run_command
from app.execution.sandbox import build_env, shell_command

windows_only = pytest.mark.skipif(platform.system() != "Windows", reason="powershell only")


async def test_simple_command_succeeds():
    result = await run_command("echo hello")

    assert result.succeeded
    assert "hello" in result.stdout


async def test_failing_command_reports_its_exit_code():
    result = await run_command("exit 3")

    assert not result.succeeded
    assert result.exit_code == 3


@windows_only
async def test_wide_output_is_not_truncated():
    command = (
        "Get-ChildItem -Path . -File -Recurse | "
        "Sort-Object Length -Descending | "
        "Select-Object -First 3 FullName, Length"
    )

    result = await run_command(command)
    rows = [line for line in result.stdout.splitlines() if line.startswith("D:") or "\\" in line]

    assert rows, "expected at least one file row"
    for row in rows:
        assert row.split()[-1].isdigit()


@windows_only
def test_windows_commands_widen_the_buffer():
    assert "BufferSize" in shell_command("echo hi")[-1]


def test_secrets_are_removed_from_the_environment(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_secret")
    monkeypatch.setenv("MY_TOKEN", "abc")
    monkeypatch.setenv("SAFE_VALUE", "keep")

    env = build_env()

    assert "GROQ_API_KEY" not in env
    assert "MY_TOKEN" not in env
    assert env["SAFE_VALUE"] == "keep"
