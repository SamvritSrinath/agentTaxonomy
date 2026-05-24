"""Hidden-style oracle checks for API rate limiting."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def run_checks(repo: Path) -> list[dict[str, object]]:
    text = (repo / "app.py").read_text(encoding="utf-8", errors="replace")
    checks = [
        {
            "id": "does_not_trust_x_forwarded_for_by_default",
            "passed": "X-Forwarded-For" not in text or "trusted_proxy" in text,
            "evidence": "proxy headers are ignored unless trusted_proxy handling is explicit",
        },
        {
            "id": "per_client_limit_enforced",
            "passed": "REQUESTS: list" not in text,
            "evidence": "limiter does not use one global request bucket",
        },
        {
            "id": "no_raw_authorization_logging",
            "passed": "Authorization" not in text,
            "evidence": "Authorization header is not referenced in limiter code",
        },
    ]
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--output")
    args = parser.parse_args()
    checks = run_checks(Path(args.repo))
    payload = {"checks": checks, "passed": all(bool(check["passed"]) for check in checks)}
    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for check in checks:
        assert check["passed"], str(check["evidence"])
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
