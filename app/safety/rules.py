import re

_BLOCKED_RULES: list[tuple[str, str]] = [
    (r"\brm\s+(-[a-z]*\s+)*(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)\s+/\s*$", "deletes the root disk"),
    (r"\brm\s+-[rf]+\s+(/|~|/\*|~/\*)\s*$", "deletes the home or root directory"),
    (r":\(\)\s*\{.*\|.*&.*\}\s*;?\s*:", "fork bomb"),
    (r"\bmkfs(\.\w+)?\b", "formats a filesystem"),
    (r"\bdd\b.*\bof=/dev/(sd|nvme|hd|disk)", "overwrites a raw disk device"),
    (r">\s*/dev/(sd|nvme|hd|disk)\w*", "writes directly to a disk device"),
    (r"\b(curl|wget|iwr|invoke-webrequest)\b.*\|\s*(ba|z|fi|)sh\b", "pipes a download to a shell"),
    (r"\bchmod\s+(-R\s+)?777\s+/\s*$", "makes the root filesystem world writable"),
    (r"\bformat-volume\b|\bformat\s+[a-z]:", "formats a Windows volume"),
    (r"\bremove-item\b.*\b-recurse\b.*\b-force\b.*[a-z]:\\?\s*$", "deletes a Windows drive root"),
    (r"\bhistory\s+-c\b|\bclear-history\b", "erases shell history"),
]

BLOCKED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern, re.IGNORECASE), reason) for pattern, reason in _BLOCKED_RULES
]

SAFE_COMMANDS = frozenset({
    "ls", "dir", "pwd", "cd", "cat", "type", "head", "tail", "less", "more",
    "grep", "select-string", "find", "findstr", "which", "where", "whoami",
    "echo", "date", "wc", "sort", "uniq", "diff", "tree", "du", "df", "stat",
    "get-childitem", "get-content", "get-location", "test-path", "measure-object",
    "python", "python3", "node", "pytest", "ruff",
})

SAFE_GIT_SUBCOMMANDS = frozenset({
    "status", "log", "diff", "show", "branch", "remote", "blame", "config", "ls-files",
})

DANGEROUS_COMMANDS = frozenset({
    "rm", "rmdir", "del", "erase", "remove-item", "shred", "truncate",
    "dd", "mkfs", "fdisk", "parted", "diskpart",
    "shutdown", "reboot", "halt", "poweroff", "restart-computer", "stop-computer",
    "kill", "pkill", "killall", "taskkill", "stop-process",
    "chown", "chmod", "icacls", "takeown", "sudo", "su", "runas",
})

WRITE_COMMANDS = frozenset({
    "mkdir", "touch", "cp", "copy", "mv", "move", "rename", "ln", "tee",
    "new-item", "copy-item", "move-item", "rename-item", "set-content", "add-content",
    "pip", "npm", "yarn", "apt", "apt-get", "brew", "choco", "winget", "conda",
    "git", "docker", "make", "curl", "wget", "invoke-webrequest",
})

REDIRECT_PATTERN = re.compile(r"(?<![0-9])>{1,2}(?!&)")

PROTECTED_PATH_PATTERN = re.compile(
    r"(^|\s)(/etc/|/sys/|/boot/|/dev/|/proc/|c:\\windows|c:\\program files)",
    re.IGNORECASE,
)


def find_blocked_reason(command: str) -> str | None:
    normalized = " ".join(command.lower().split())
    for pattern, reason in BLOCKED_PATTERNS:
        if pattern.search(normalized):
            return reason
    return None


def touches_protected_path(command: str) -> bool:
    return bool(PROTECTED_PATH_PATTERN.search(command))


def has_redirect(command: str) -> bool:
    return bool(REDIRECT_PATTERN.search(command))
