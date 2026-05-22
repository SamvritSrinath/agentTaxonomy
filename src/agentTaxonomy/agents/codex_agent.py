"""Codex command adapter driven by the ``CAT_CODEX_CMD`` environment variable."""

from __future__ import annotations

from agentTaxonomy.env import getenv

from .command_agent import CommandAgentAdapter
from .sandbox import SandboxProfile


class CodexAgentAdapter(CommandAgentAdapter):
    """Run Codex as an external command without hard-coding fragile CLI flags."""

    def __init__(self, sandbox_profile: SandboxProfile | None = None) -> None:
        """Initialize Codex from ``CAT_CODEX_CMD`` or a conservative default."""
        command = getenv("CAT_CODEX_CMD", fallbacks=("UAB_CODEX_CMD",), default="codex < {prompt_file}")
        super().__init__("codex", command, sandbox_profile=sandbox_profile)
