#!/usr/bin/env python3
"""Report OpenRouter API key usage and remaining credits.

Fetches usage for the key in ``OPENROUTER_API_KEY`` (or ``--api-key``) via
``GET https://openrouter.ai/api/v1/key``. If the key is a management key,
also fetches account-level credits from ``GET /api/v1/credits``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"
OPENROUTER_CREDITS_URL = "https://openrouter.ai/api/v1/credits"


def _get_json(url: str, api_key: str, *, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter request failed with HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc}") from exc


def _resolve_api_key(explicit: str | None) -> str:
    key = explicit or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError(
            "No API key provided. Set OPENROUTER_API_KEY or pass --api-key."
        )
    return key


def _fmt_usd(value: float | int | None) -> str:
    if value is None:
        return "unlimited"
    return f"${value:.4f}"


def _print_key_usage(data: dict[str, Any]) -> None:
    label = data.get("label", "(unknown key)")
    print(f"Key: {label}")

    flags: list[str] = []
    if data.get("is_management_key"):
        flags.append("management")
    if data.get("is_provisioning_key"):
        flags.append("provisioning")
    if data.get("is_free_tier"):
        flags.append("free tier")
    if flags:
        print(f"Type: {', '.join(flags)}")

    if data.get("expires_at"):
        print(f"Expires: {data['expires_at']}")

    limit = data.get("limit")
    limit_remaining = data.get("limit_remaining")
    if limit is not None or limit_remaining is not None:
        reset = data.get("limit_reset") or "period"
        print(f"Limit ({reset}): {_fmt_usd(limit)}")
        print(f"Remaining: {_fmt_usd(limit_remaining)}")

    print()
    print("Usage (USD):")
    for period in ("usage", "usage_daily", "usage_weekly", "usage_monthly"):
        if period in data:
            name = period.removeprefix("usage_") or "all time"
            print(f"  {name:8} {_fmt_usd(data[period])}")

    byok = data.get("byok_usage")
    if byok:
        print()
        print("BYOK usage (USD):")
        for period in ("byok_usage", "byok_usage_daily", "byok_usage_weekly", "byok_usage_monthly"):
            if period in data and data[period]:
                name = period.removeprefix("byok_usage_") or "all time"
                print(f"  {name:8} {_fmt_usd(data[period])}")

    rate_limit = data.get("rate_limit")
    if isinstance(rate_limit, dict) and rate_limit.get("requests") is not None:
        interval = rate_limit.get("interval", "?")
        print()
        print(f"Rate limit: {rate_limit['requests']} requests / {interval}")


def _print_account_credits(data: dict[str, Any]) -> None:
    total_credits = data.get("total_credits")
    total_usage = data.get("total_usage")
    if total_credits is None and total_usage is None:
        return
    print()
    print("Account credits (management key):")
    print(f"  purchased  {_fmt_usd(total_credits)}")
    print(f"  used       {_fmt_usd(total_usage)}")
    if total_credits is not None and total_usage is not None:
        remaining = total_credits - total_usage
        print(f"  remaining  {_fmt_usd(remaining)}")


def fetch_usage(api_key: str, *, timeout: float = 30.0) -> dict[str, Any]:
    """Return key usage and optional account credits from OpenRouter."""
    result: dict[str, Any] = {"key": _get_json(OPENROUTER_KEY_URL, api_key, timeout=timeout)}

    key_data = result["key"].get("data", {})
    if key_data.get("is_management_key"):
        try:
            result["credits"] = _get_json(OPENROUTER_CREDITS_URL, api_key, timeout=timeout)
        except RuntimeError as exc:
            result["credits_error"] = str(exc)

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Show OpenRouter usage for the current API key.",
    )
    parser.add_argument(
        "--api-key",
        help="OpenRouter API key (default: OPENROUTER_API_KEY env var).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON response instead of a human-readable summary.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds (default: 30).",
    )
    args = parser.parse_args(argv)

    try:
        api_key = _resolve_api_key(args.api_key)
        payload = fetch_usage(api_key, timeout=args.timeout)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    key_data = payload["key"].get("data")
    if not key_data:
        print("Unexpected response: no key data.", file=sys.stderr)
        print(json.dumps(payload["key"], indent=2), file=sys.stderr)
        return 1

    _print_key_usage(key_data)

    credits = payload.get("credits")
    if credits:
        _print_account_credits(credits.get("data", {}))
    elif payload.get("credits_error"):
        print()
        print(f"(Could not fetch account credits: {payload['credits_error']})", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
