import shlex
from pathlib import Path

from app.safety.models import RiskLevel, SafetyVerdict
from app.safety.rules import (
    DANGEROUS_COMMANDS,
    INSTALL_COMMANDS,
    NETWORK_COMMANDS,
    PIPE_ONLY_COMMANDS,
    SAFE_COMMANDS,
    SAFE_GIT_SUBCOMMANDS,
    WRITE_COMMANDS,
    find_blocked_reason,
    has_redirect,
    touches_protected_path,
)

CHAIN_SEPARATORS = ("&&", "||", ";", "|")
PIPE_SEPARATOR = "|"

SHELL_WRAPPERS = frozenset({"powershell", "pwsh", "cmd", "bash", "sh", "zsh"})
MAX_UNWRAP_DEPTH = 3

GIT_FLAGS_WITH_VALUE = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})
COMMAND_FLAGS = frozenset({"-command", "-c", "-file", "-f", "/c", "/k"})

PYTHON_RUNNERS = frozenset({"python", "python3", "py"})
SAFE_PYTHON_MODULES = frozenset({"pytest", "ruff", "mypy", "json.tool"})

READ_ONLY_TOOLS = frozenset({"read_file", "list_directory", "git_status", "git_diff", "git_log"})
WRITE_TOOLS = frozenset({"write_file"})


def classify_tool_call(tool_name: str, arguments: dict) -> SafetyVerdict:
    if tool_name in READ_ONLY_TOOLS:
        return SafetyVerdict(RiskLevel.SAFE, "read-only tool")

    if tool_name in WRITE_TOOLS:
        path = str(arguments.get("path", ""))
        if touches_protected_path(path):
            return SafetyVerdict(RiskLevel.DANGEROUS, "writes to a protected system path")
        return SafetyVerdict(RiskLevel.CAUTION, "writes to a file")

    command = str(arguments.get("command", "")).strip()
    if not command:
        return SafetyVerdict(RiskLevel.CAUTION, "unrecognised tool call")

    return classify_command(command)


def classify_command(command: str) -> SafetyVerdict:
    command = _unwrap_shell(command.strip())
    if not command:
        return SafetyVerdict(RiskLevel.SAFE, "empty command")

    if reason := find_blocked_reason(command):
        return SafetyVerdict(RiskLevel.BLOCKED, reason)

    segments = _split_chain(command)
    if len(segments) > 1:
        return _worst_of(segments, _is_pipeline(command))

    return _classify_single(command)


def _unwrap_shell(command: str) -> str:
    for _ in range(MAX_UNWRAP_DEPTH):
        tokens = _tokenize(command)
        if not tokens or _base_name(tokens[0]) not in SHELL_WRAPPERS:
            return command

        inner = _inner_command(tokens[1:])
        if not inner:
            return command

        command = inner.strip("\"'")

    return command


def _is_pipeline(command: str) -> bool:
    return PIPE_SEPARATOR in command and not any(
        separator in command for separator in ("&&", "||", ";")
    )


def _classify_single(command: str) -> SafetyVerdict:
    tokens = _strip_call_operator(_tokenize(command))
    if not tokens:
        return SafetyVerdict(RiskLevel.CAUTION, "could not parse the command")

    name = _base_name(tokens[0])
    if name in PYTHON_RUNNERS:
        return _classify_python(tokens)

    if name in DANGEROUS_COMMANDS:
        if touches_protected_path(command):
            return SafetyVerdict(RiskLevel.DANGEROUS, f"{name} targets a protected system path")
        return SafetyVerdict(RiskLevel.DANGEROUS, f"{name} can destroy data or stop processes")

    if name == "git":
        return _classify_git(tokens)

    if has_redirect(command):
        return SafetyVerdict(RiskLevel.CAUTION, "redirects output into a file")

    if name in NETWORK_COMMANDS:
        return SafetyVerdict(RiskLevel.CAUTION, f"{name} sends a request over the network")

    if name in INSTALL_COMMANDS:
        return SafetyVerdict(RiskLevel.CAUTION, f"{name} installs or removes packages")

    if name in WRITE_COMMANDS:
        return SafetyVerdict(RiskLevel.CAUTION, f"{name} modifies files")

    if name in SAFE_COMMANDS or name in PIPE_ONLY_COMMANDS:
        return SafetyVerdict(RiskLevel.SAFE, f"{name} only reads")

    return SafetyVerdict(RiskLevel.CAUTION, f"{name} is not a known read-only command")


def _strip_call_operator(tokens: list[str]) -> list[str]:
    return tokens[1:] if tokens and tokens[0] == "&" else tokens


def _classify_python(tokens: list[str]) -> SafetyVerdict:
    if "-c" in tokens or "-" in tokens[1:]:
        return SafetyVerdict(RiskLevel.CAUTION, "runs python code given inline")

    if "-m" in tokens:
        module = _base_name(tokens[tokens.index("-m") + 1]) if len(tokens) > 2 else ""
        if module in INSTALL_COMMANDS:
            return SafetyVerdict(RiskLevel.CAUTION, f"{module} installs or removes packages")
        if module in SAFE_PYTHON_MODULES:
            return SafetyVerdict(RiskLevel.SAFE, f"python -m {module} only reads")
        return SafetyVerdict(RiskLevel.CAUTION, f"runs the python module {module or 'given'}")

    return SafetyVerdict(RiskLevel.CAUTION, "runs a python script")


def _classify_git(tokens: list[str]) -> SafetyVerdict:
    subcommand = _git_subcommand(tokens[1:])
    if subcommand in SAFE_GIT_SUBCOMMANDS:
        return SafetyVerdict(RiskLevel.SAFE, f"git {subcommand} only reads")
    if subcommand in {"push", "reset", "clean", "rebase"}:
        return SafetyVerdict(RiskLevel.DANGEROUS, f"git {subcommand} can discard or publish work")
    return SafetyVerdict(RiskLevel.CAUTION, f"git {subcommand or 'command'} changes the repository")


def _inner_command(tokens: list[str]) -> str:
    for index, token in enumerate(tokens):
        if token.lower() in COMMAND_FLAGS and index + 1 < len(tokens):
            return tokens[index + 1]

    return next((token for token in reversed(tokens) if not token.startswith("-")), "")


def _git_subcommand(tokens: list[str]) -> str:
    skip_next = False

    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token in GIT_FLAGS_WITH_VALUE:
            skip_next = True
            continue
        if not token.startswith("-"):
            return token

    return ""


def _worst_of(segments: list[str], is_pipeline: bool = False) -> SafetyVerdict:
    verdicts = [_classify_single(segment) for segment in segments]
    order = [RiskLevel.BLOCKED, RiskLevel.DANGEROUS, RiskLevel.CAUTION, RiskLevel.SAFE]
    label = "pipeline" if is_pipeline else "chained command"

    for level in order:
        if match := next((v for v in verdicts if v.risk is level), None):
            if level is RiskLevel.SAFE:
                return SafetyVerdict(level, f"every part of the {label} only reads")
            return SafetyVerdict(level, f"{label}: {match.reason}")

    return SafetyVerdict(RiskLevel.CAUTION, label)


def _split_chain(command: str) -> list[str]:
    segments = [command]
    for separator in CHAIN_SEPARATORS:
        segments = [part for segment in segments for part in segment.split(separator)]
    return [segment.strip() for segment in segments if segment.strip()]


def _tokenize(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=False)
    except ValueError:
        return command.split()


def _base_name(token: str) -> str:
    return Path(token.strip("\"'")).name.lower().removesuffix(".exe")
