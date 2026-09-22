class TerminalAgentError(Exception):
    pass


class ConfigurationError(TerminalAgentError):
    pass


class LLMError(TerminalAgentError):
    pass


class ToolExecutionError(TerminalAgentError):
    pass


class CommandTimeoutError(ToolExecutionError):
    def __init__(self, command: str, timeout: int) -> None:
        self.command = command
        self.timeout = timeout
        super().__init__(f"Command timed out after {timeout}s: {command}")


class BlockedCommandError(TerminalAgentError):
    def __init__(self, command: str, reason: str) -> None:
        self.command = command
        self.reason = reason
        super().__init__(f"Command blocked: {reason}")


class SessionNotFoundError(TerminalAgentError):
    def __init__(self, thread_id: str) -> None:
        self.thread_id = thread_id
        super().__init__(f"No session found for thread: {thread_id}")
