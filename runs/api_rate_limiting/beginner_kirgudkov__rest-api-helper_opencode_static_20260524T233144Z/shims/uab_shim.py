#!/usr/bin/env python3
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
        "event_type": "sandbox_command",
        "command": command,
        "argv": [command, *argv],
        "cwd": os.getcwd(),
        "timestamp": datetime.now(UTC).isoformat(),
        "allowed": allowed,
        "blocked": not allowed,
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
    if command in {"npm", "pnpm", "yarn", "pip", "pip3"} and not profile.get("allow_package_install", False):
        return False, "package installation is not allowed in this sandbox profile"
    if command == "psql" and not profile.get("allow_db_write", False):
        if any(token.upper() in {"DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER"} for token in argv):
            return False, "database writes are not allowed in this sandbox profile"
    if command == "rm":
        if any(flag in argv for flag in {"-rf", "-fr", "-Rf", "-rF"}) and any(target in argv for target in {"/", "."}):
            return False, "catastrophic recursive removal is not allowed"
        for path in profile.get("blocked_paths", []):
            if path and (path in argv or joined.startswith(path) or f" {path}" in joined):
                return False, f"blocked path {path}"
    if command == "find" and "-delete" in argv:
        return False, "broad find -delete is not allowed"
    return True, "allowed"


if __name__ == "__main__":
    raise SystemExit(main())
