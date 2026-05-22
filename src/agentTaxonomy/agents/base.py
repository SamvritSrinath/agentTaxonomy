"""Shared protocol types for external coding-agent adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class AgentRunRequest:
    """Inputs required to execute an external command agent."""

    run_id: str
    instance_id: str
    prompt: str
    worktree: Path
    output_dir: Path
    timeout_seconds: int
    env: Mapping[str, str]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class AgentRunResult:
    """Result metadata emitted by an agent adapter execution."""

    exit_code: int
    stdout_path: Path
    stderr_path: Path
    started_at: str
    completed_at: str
    metadata: dict[str, Any]


class AgentAdapter(Protocol):
    """Protocol implemented by concrete command-agent adapters."""

    name: str

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        """Execute the agent and return captured process metadata."""
        ...
