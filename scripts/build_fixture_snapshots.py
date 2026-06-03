"""Build or validate local fixture snapshots."""

from __future__ import annotations

import argparse
import json

from agentTaxonomy.fixture_builder import build_fixtures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="benchmark/repo_sources.yaml")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    result = build_fixtures(args.sources, download=args.download)
    print(json.dumps(result, indent=2))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
