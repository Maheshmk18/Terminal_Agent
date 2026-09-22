import shlex
from pathlib import Path

from app.safety.models import RiskLevel, SafetyVerdict
from app.safety.rules import (
    DANGEROUS_COMMANDS,
    SAFE_COMMANDS,
    SAFE_GIT_SUBCOMMANDS,
    WRITE_COMMANDS,
    find_blocked_reason,
    has_redirect,
    touches_protected_path,
)

CHAIN_SEPARATORS = ("&&", "||", ";", "|")

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
    command = command.strip()
    if not command:
        return SafetyVerdict(RiskLevel.SAFE, "empty command")

    if reason := find_blocked_reason(command):
        return SafetyVerdict(RiskLevel.BLOCKED, reason)

    segments = _split_chain(command)
    if len(segments) > 1:
        return _worst_of(segments)

    return _classify_single(command)


def _classify_single(command: str) -> SafetyVerdict:
    tokens = _tokenize(command)
    if not tokens:
        return SafetyVerdict(RiskLevel.CAUTION, "could not parse the command")

    name = _base_name(tokens[0])

    if name in DANGEROUS_COMMANDS:
        if touches_protected_path(command):
            return SafetyVerdict(RiskLevel.DANGEROUS, f"{name} targets a protected system path")
        return SafetyVerdict(RiskLevel.DANGEROUS, f"{name} can destroy data or stop processes")

    if name == "git":
        return _classify_git(tokens)

    if has_redirect(command):
        return SafetyVerdict(RiskLevel.CAUTION, "redirects output into a file")

    if name in WRITE_COMMANDS:
        return SafetyVerdict(RiskLevel.CAUTION, f"{name} modifies files or installs packages")

    if name in SAFE_COMMANDS:
        return SafetyVerdict(RiskLevel.SAFE, f"{name} only reads")

    return SafetyVerdict(RiskLevel.CAUTION, f"{name} is not a known read-only command")


def _classify_git(tokens: list[str]) -> SafetyVerdict:
    subcommand = next((token for token in tokens[1:] if not token.startswith("-")), "")
    if subcommand in SAFE_GIT_SUBCOMMANDS:
        return SafetyVerdict(RiskLevel.SAFE, f"git {subcommand} only reads")
    if subcommand in {"push", "reset", "clean", "rebase"}:
        return SafetyVerdict(RiskLevel.DANGEROUS, f"git {subcommand} can discard or publish work")
    return SafetyVerdict(RiskLevel.CAUTION, f"git {subcommand or 'command'} changes the repository")


def _worst_of(segments: list[str]) -> SafetyVerdict:
    verdicts = [_classify_single(segment) for segment in segments]
    order = [RiskLevel.BLOCKED, RiskLevel.DANGEROUS, RiskLevel.CAUTION, RiskLevel.SAFE]

    for level in order:
        if match := next((v for v in verdicts if v.risk is level), None):
            if level is RiskLevel.SAFE:
                return SafetyVerdict(level, "all parts of the chain only read")
            return SafetyVerdict(level, f"chained command: {match.reason}")

    return SafetyVerdict(RiskLevel.CAUTION, "chained command")


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
