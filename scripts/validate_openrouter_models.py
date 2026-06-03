"""Validate configured OpenRouter model ids."""

from __future__ import annotations

import argparse
import json

from agentTaxonomy.model_validation import validate_models


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="benchmark/configs/models.yaml")
    args = parser.parse_args()
    result = validate_models(args.models)
    print(json.dumps(result, indent=2))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
