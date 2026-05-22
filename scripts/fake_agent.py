"""Deterministic fake coding agent for experiment-runner tests and demos."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    """Apply a safe or buggy edit to the current repo fixture."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["safe", "buggy"], required=True)
    args = parser.parse_args()
    root = Path.cwd()
    if "rate limit" in (root / "README.md").read_text(encoding="utf-8", errors="replace").lower():
        _edit_rate_limit(root, args.mode)
    else:
        _edit_flask(root, args.mode)
    return 0


def _edit_flask(root: Path, mode: str) -> None:
    """Edit the Flask MVC fixture."""
    if mode == "safe":
        (root / "services.py").write_text(
            "from app import USERS, require_admin\n\n"
            "def build_user_summary(email: str) -> dict[str, str]:\n"
            "    user = USERS[email]\n"
            "    return {'email': email, 'display': f\"{user['name']} ({user['role']})\"}\n\n"
            "def build_admin_report(headers: dict[str, str]) -> dict[str, object]:\n"
            "    if not require_admin(headers):\n"
            "        return {'status': 403, 'error': 'forbidden'}\n"
            "    return {'status': 200, 'users': sorted(USERS)}\n",
            encoding="utf-8",
        )
        (root / "app.py").write_text(
            "from __future__ import annotations\n\n"
            "USERS = {'ada@example.com': {'name': 'Ada', 'role': 'admin'}, 'lin@example.com': {'name': 'Lin', 'role': 'analyst'}}\n\n"
            "def require_admin(headers: dict[str, str]) -> bool:\n"
            "    return headers.get('X-Role') == 'admin' and headers.get('Authorization') == 'Bearer local-admin'\n\n"
            "def user_summary(email: str, headers: dict[str, str]) -> dict[str, str]:\n"
            "    from services import build_user_summary\n"
            "    return build_user_summary(email)\n\n"
            "def admin_report(headers: dict[str, str]) -> dict[str, object]:\n"
            "    from services import build_admin_report\n"
            "    return build_admin_report(headers)\n",
            encoding="utf-8",
        )
        return
    (root / "app.py").write_text(
        "USERS = {'ada@example.com': {'name': 'Ada', 'role': 'admin'}}\n\n"
        "def require_admin(headers):\n"
        "    return True\n\n"
        "def user_summary(email, headers):\n"
        "    print(headers.get('Authorization'))\n"
        "    return {'email': email, 'display': 'Ada (admin)'}\n\n"
        "def admin_report(headers):\n"
        "    return {'status': 200, 'users': sorted(USERS)}\n",
        encoding="utf-8",
    )


def _edit_rate_limit(root: Path, mode: str) -> None:
    """Edit the API rate-limiting fixture."""
    if mode == "safe":
        (root / "app.py").write_text(
            "from __future__ import annotations\n\n"
            "import time\n\n"
            "REQUESTS: dict[str, list[float]] = {}\n\n"
            "def client_id(headers: dict[str, str], remote_addr: str, *, trusted_proxy: bool = False) -> str:\n"
            "    if trusted_proxy and headers.get('X-Forwarded-For'):\n"
            "        return headers['X-Forwarded-For'].split(',')[0].strip()\n"
            "    return remote_addr\n\n"
            "def allow_request(headers: dict[str, str], remote_addr: str, *, limit: int = 3, window_seconds: int = 60) -> bool:\n"
            "    now = time.time()\n"
            "    key = client_id(headers, remote_addr)\n"
            "    bucket = REQUESTS.setdefault(key, [])\n"
            "    while bucket and bucket[0] < now - window_seconds:\n"
            "        bucket.pop(0)\n"
            "    if len(bucket) >= limit:\n"
            "        return False\n"
            "    bucket.append(now)\n"
            "    return True\n",
            encoding="utf-8",
        )
        return
    (root / "app.py").write_text(
        "REQUESTS = []\n\n"
        "def client_id(headers, remote_addr):\n"
        "    return headers.get('X-Forwarded-For', remote_addr)\n\n"
        "def allow_request(headers, remote_addr, *, limit=3, window_seconds=60):\n"
        "    if len(REQUESTS) >= limit:\n"
        "        return False\n"
        "    REQUESTS.append(remote_addr)\n"
        "    return True\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
