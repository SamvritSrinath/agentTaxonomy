"""Agent adapter interfaces and implementations for repo-task executions."""

from .base import AgentRunRequest, AgentRunResult
from .codex_agent import CodexAgentAdapter
from .command_agent import CommandAgentAdapter
from .sandbox import SandboxProfile

__all__ = [
    "AgentRunRequest",
    "AgentRunResult",
    "CodexAgentAdapter",
    "CommandAgentAdapter",
    "SandboxProfile",
]
