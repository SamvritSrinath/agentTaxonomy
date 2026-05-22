#!/usr/bin/env python3
"""CLI wrapper for OpenRouter usage reporting (implementation in agentTaxonomy)."""

from __future__ import annotations

import argparse
import json
import sys

from agentTaxonomy.openrouter_usage import fetch_usage, resolve_api_key


def _fmt_usd(value: float | int | None) -> str:
    if value is None:
        return "unlimited"
    return f"${value:.4f}"


def _print_key_usage(data: dict) -> None:
    label = data.get("label", "(unknown key)")
    print(f"Key: {label}")
    if data.get("usage_monthly") is not None:
        print(f"  monthly  {_fmt_usd(data['usage_monthly'])}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show OpenRouter usage for the current API key.")
    parser.add_argument("--api-key", help="OpenRouter API key (default: OPENROUTER_API_KEY env var).")
    parser.add_argument("--json", action="store_true", help="Print raw JSON response.")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    try:
        api_key = resolve_api_key(args.api_key)
        payload = fetch_usage(api_key, timeout=args.timeout)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0
    key_data = payload["key"].get("data", {})
    if not key_data:
        print("Unexpected response: no key data.", file=sys.stderr)
        return 1
    _print_key_usage(key_data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
