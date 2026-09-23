from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    SAFE = "safe"
    CAUTION = "caution"
    DANGEROUS = "dangerous"
    BLOCKED = "blocked"

    @property
    def needs_approval(self) -> bool:
        return self in (RiskLevel.CAUTION, RiskLevel.DANGEROUS)


@dataclass(frozen=True)
class SafetyVerdict:
    risk: RiskLevel
    reason: str

    @property
    def is_blocked(self) -> bool:
        return self.risk is RiskLevel.BLOCKED


@dataclass(frozen=True)
class PendingCall:
    call_id: str
    tool_name: str
    arguments: dict
    verdict: SafetyVerdict

    @property
    def display(self) -> str:
        if command := self.arguments.get("command"):
            return str(command)
        args = ", ".join(f"{key}={value!r}" for key, value in self.arguments.items())
        return f"{self.tool_name}({args})"
