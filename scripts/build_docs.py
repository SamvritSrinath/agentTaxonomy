#!/usr/bin/env python3
"""Build or serve the MkDocs documentation site via uv."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    serve = "--serve" in sys.argv
    uv = shutil.which("uv")
    if not uv:
        print("uv is required. Install: https://docs.astral.sh/uv/getting-started/installation/", file=sys.stderr)
        return 1

    # Regenerate docs/api/*.md stubs and mkdocs API nav from src/agentTaxonomy.
    sys.path.insert(0, str(root / "scripts"))
    from generate_api_stubs import generate_all  # noqa: E402

    generate_all(root)

    mkdocs_args = ["serve", "--dev-addr", "127.0.0.1:8000"] if serve else ["build", "--clean"]
    command = [uv, "run", "--group", "docs", "mkdocs", *mkdocs_args]

    if serve:
        print("Serving documentation at http://127.0.0.1:8000")
    else:
        print("Building documentation:", " ".join(command))

    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    subprocess.run(command, cwd=root, env=env, check=True)

    if not serve:
        index = root / "site" / "index.html"
        print(f"\nDone. Open:\n  file://{index}")
        print("Or run: uv run --group docs mkdocs serve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
