"""Sandbox profile and command-shim helpers for repo-task executions."""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SandboxProfile:
    """Policy controlling which command attempts are logged or blocked."""

    name: str = "class_b_repo_edit"
    network: str = "disabled"
    allow_git_push: bool = False
    allow_package_install: bool = True
    allow_db_write: bool = False
    allow_external_http: bool = False
    blocked_paths: list[str] = field(default_factory=lambda: ["/etc", "/root", "/workspace/secrets"])
    logged_commands: list[str] = field(
        default_factory=lambda: ["git", "rm", "curl", "wget", "npm", "pip", "psql"]
    )

    def to_policy(self) -> dict[str, Any]:
        """Return a JSON-serializable policy dictionary."""
        return asdict(self)

    def profile_hash(self) -> str:
        """Return a stable hash of this sandbox policy."""
        return sha256(json.dumps(self.to_policy(), sort_keys=True).encode("utf-8")).hexdigest()

    def write_metadata(self, output_dir: Path) -> Path:
        """Write ``sandbox_profile.json`` into a run output directory."""
        payload = {**self.to_policy(), "profile_hash": self.profile_hash()}
        path = output_dir / "sandbox_profile.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path


def profile_by_name(name: str | None) -> SandboxProfile:
    """Return a named sandbox profile, defaulting to the class-B repo-edit policy."""
    if name in {None, "", "class_b_repo_edit", "repo_task_default"}:
        return SandboxProfile()
    if name == "class_c_local_services":
        return SandboxProfile(
            name="class_c_local_services",
            network="local_only",
            allow_db_write=True,
            allow_external_http=False,
        )
    if name == "class_a_read_only":
        return SandboxProfile(
            name="class_a_read_only",
            network="disabled",
            allow_package_install=False,
            allow_db_write=False,
        )
    return SandboxProfile(name=name)


def install_command_shims(profile: SandboxProfile, output_dir: Path, base_env: dict[str, str]) -> dict[str, str]:
    """Create command wrappers and return an environment with the shim path first."""
    shim_dir = output_dir / "shims"
    shim_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "sandbox_events.jsonl"
    real_bins = {
        command: shutil.which(command, path=base_env.get("PATH") or os.environ.get("PATH", ""))
        for command in profile.logged_commands
    }
    config_path = shim_dir / "shim_config.json"
    config_path.write_text(
        json.dumps(
            {
                "profile": profile.to_policy(),
                "profile_hash": profile.profile_hash(),
                "log_path": str(log_path),
                "real_bins": real_bins,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    shim_py = shim_dir / "uab_shim.py"
    shim_py.write_text(_SHIM_SCRIPT, encoding="utf-8")
    shim_py.chmod(0o755)
    for command in profile.logged_commands:
        wrapper = shim_dir / command
        wrapper.write_text(
            f"#!/bin/sh\nexec {json.dumps(sys.executable)} {json.dumps(str(shim_py))} "
            f"{json.dumps(str(config_path))} {json.dumps(command)} \"$@\"\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
    env = dict(base_env)
    env["PATH"] = f"{shim_dir}{os.pathsep}{env.get('PATH', '')}"
    env["CAT_SANDBOX_PROFILE"] = profile.name
    env["CAT_SANDBOX_PROFILE_HASH"] = profile.profile_hash()
    env["CAT_SANDBOX_LOG"] = str(log_path)
    return env


_SHIM_SCRIPT = r'''#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    config_path = Path(sys.argv[1])
    command = sys.argv[2]
    argv = sys.argv[3:]
    config = json.loads(config_path.read_text(encoding="utf-8"))
    profile = config["profile"]
    real_bin = config["real_bins"].get(command)
    allowed, reason = decision(command, argv, profile)
    event = {
        "event_type": "command",
        "argv": [command, *argv],
        "cwd": os.getcwd(),
        "timestamp": datetime.now(UTC).isoformat(),
        "allowed": allowed,
        "reason": reason,
        "sandbox_profile": profile["name"],
        "sandbox_profile_hash": config["profile_hash"],
    }
    with Path(config["log_path"]).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")
    if not allowed:
        print(f"cat sandbox blocked {command}: {reason}", file=sys.stderr)
        return 126
    if not real_bin:
        print(f"cat sandbox could not find real binary for {command}", file=sys.stderr)
        return 127
    completed = subprocess.run([real_bin, *argv], check=False)
    return completed.returncode


def decision(command: str, argv: list[str], profile: dict) -> tuple[bool, str]:
    joined = " ".join(argv)
    if command in {"curl", "wget"}:
        if profile.get("network") == "disabled" or not profile.get("allow_external_http", False):
            return False, "external HTTP is not allowed in this sandbox profile"
    if command == "git" and "push" in argv and not profile.get("allow_git_push", False):
        return False, "git push is not allowed in this sandbox profile"
    if command in {"npm", "pip"} and not profile.get("allow_package_install", False):
        return False, "package installation is not allowed in this sandbox profile"
    if command == "psql" and not profile.get("allow_db_write", False):
        if any(token.upper() in {"DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER"} for token in argv):
            return False, "database writes are not allowed in this sandbox profile"
    if command == "rm":
        for path in profile.get("blocked_paths", []):
            if path and (path in argv or joined.startswith(path) or f" {path}" in joined):
                return False, f"blocked path {path}"
    return True, "allowed"


if __name__ == "__main__":
    raise SystemExit(main())
'''
