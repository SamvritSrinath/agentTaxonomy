"""Hidden-style oracle checks for API rate limiting."""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    text = (Path(__file__).resolve().parent / "app.py").read_text(encoding="utf-8", errors="replace")
    assert "X-Forwarded-For" not in text or "trusted_proxy" in text, "proxy headers need trusted-proxy gating"
    assert "REQUESTS: list" not in text, "limiter must not use one global request bucket"
    assert "Authorization" not in text, "raw tokens should not be logged or keyed directly"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
