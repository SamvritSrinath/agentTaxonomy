"""Generic external command adapter for local coding agents."""

from __future__ import annotations

import os
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .base import AgentRunRequest, AgentRunResult
from .sandbox import SandboxProfile, install_command_shims


class CommandAgentAdapter:
    """Run an arbitrary shell command against an isolated worktree."""

    def __init__(self, name: str, command_template: str, sandbox_profile: SandboxProfile | None = None) -> None:
        """Initialize the adapter with a display name, command, and sandbox policy."""
        self.name = name
        self.command_template = command_template
        self.sandbox_profile = sandbox_profile or SandboxProfile()

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        """Execute the configured command and capture stdout/stderr separately."""
        request.output_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = Path(str(request.metadata.get("prompt_file") or request.output_dir / "prompt.md"))
        if not prompt_path.exists():
            prompt_path.write_text(request.prompt, encoding="utf-8")
        stdout_path = request.output_dir / "stdout.txt"
        stderr_path = request.output_dir / "stderr.txt"
        self.sandbox_profile.write_metadata(request.output_dir)

        env = dict(os.environ)
        env.update(request.env)
        env = install_command_shims(self.sandbox_profile, request.output_dir, env)
        command = self._expand_command(request, prompt_path)
        if request.metadata.get("docker_sandbox"):
            command = self._docker_command(command, request)
        started_at = datetime.now(UTC).isoformat()
        with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
            try:
                result = subprocess.run(
                    command,
                    cwd=request.worktree,
                    shell=True,
                    env=env,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=request.timeout_seconds,
                    check=False,
                    text=True,
                )
                exit_code = result.returncode
                timed_out = False
            except subprocess.TimeoutExpired:
                stderr.write("\ncommand timed out\n")
                exit_code = 124
                timed_out = True
        completed_at = datetime.now(UTC).isoformat()
        return AgentRunResult(
            exit_code=exit_code,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            started_at=started_at,
            completed_at=completed_at,
            metadata={
                "command": command,
                "timed_out": timed_out,
                "sandbox_profile_name": self.sandbox_profile.name,
                "sandbox_profile_hash": self.sandbox_profile.profile_hash(),
            },
        )

    def _expand_command(self, request: AgentRunRequest, prompt_path) -> str:
        """Expand placeholders supported by command-agent templates."""
        return (
            self.command_template.replace("{prompt_file}", str(prompt_path))
            .replace("{worktree}", str(request.worktree))
            .replace("{output_dir}", str(request.output_dir))
            .replace("{instance_id}", request.instance_id)
        )

    def _docker_command(self, command: str, request: AgentRunRequest) -> str:
        """Wrap an agent command in a local Docker container with no network."""
        user = f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else "1000:1000"
        return " ".join(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--user",
                shlex.quote(user),
                "-v",
                shlex.quote(f"{request.worktree}:{request.worktree}"),
                "-v",
                shlex.quote(f"{request.output_dir}:{request.output_dir}"),
                "-w",
                shlex.quote(str(request.worktree)),
                "-e",
                shlex.quote(f"PATH={request.output_dir / 'shims'}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"),
                "-e",
                shlex.quote(f"CAT_SANDBOX_PROFILE={self.sandbox_profile.name}"),
                "-e",
                shlex.quote(f"CAT_SANDBOX_PROFILE_HASH={self.sandbox_profile.profile_hash()}"),
                "-e",
                shlex.quote(f"CAT_SANDBOX_LOG={request.output_dir / 'sandbox_events.jsonl'}"),
                "python:3.11-slim",
                "sh",
                "-lc",
                shlex.quote(command),
            ]
        )
