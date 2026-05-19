"""Extract fenced code blocks from generative markdown into audit-ready artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

FENCE_PATTERN = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)

LANG_EXTENSIONS: dict[str, str] = {
    "scala": ".scala",
    "python": ".py",
    "py": ".py",
    "bash": ".sh",
    "sh": ".sh",
    "shell": ".sh",
    "csv": ".csv",
    "sql": ".sql",
    "javascript": ".js",
    "js": ".js",
    "typescript": ".ts",
    "ts": ".ts",
    "dockerfile": ".dockerfile",
    "yaml": ".yml",
    "yml": ".yml",
    "json": ".json",
    "sbt": ".sbt",
    "text": ".txt",
    "txt": ".txt",
    "markdown": ".md",
    "md": ".md",
}


def extract_markdown_artifacts(markdown_path: Path, output_dir: Path) -> dict[str, Any]:
    """Write fenced blocks from a markdown file into ``output_dir``.

    Args:
        markdown_path: Source file (typically ``agent_output.md``).
        output_dir: Directory for extracted files (for example ``extracted/``).

    Returns:
        Manifest dict with ``extracted_files``, ``block_count``, and ``output_dir``.
    """
    text = markdown_path.read_text(encoding="utf-8", errors="replace")
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted_files: list[dict[str, str]] = []
    prose_path = output_dir / "explanation.md"
    prose_parts: list[str] = []

    last_end = 0
    block_index = 0
    for match in FENCE_PATTERN.finditer(text):
        prose_parts.append(text[last_end : match.start()])
        last_end = match.end()
        block_index += 1
        lang = match.group(1).strip().lower().split()[0] if match.group(1).strip() else "text"
        body = match.group(2).rstrip("\n")
        if not body.strip():
            continue
        ext = LANG_EXTENSIONS.get(lang, ".txt")
        filename = _filename_for_block(lang, body, block_index, ext)
        target = output_dir / filename
        if target.exists():
            target = output_dir / f"{target.stem}_{block_index}{ext}"
        target.write_text(body + "\n", encoding="utf-8")
        extracted_files.append(
            {
                "source": str(markdown_path),
                "language": lang,
                "relative_path": str(target.relative_to(output_dir)),
            }
        )

    prose_parts.append(text[last_end:])
    prose = "\n".join(part.strip() for part in prose_parts if part.strip())
    if prose:
        prose_path.write_text(prose + "\n", encoding="utf-8")
        extracted_files.append(
            {
                "source": str(markdown_path),
                "language": "markdown",
                "relative_path": prose_path.name,
            }
        )

    return {
        "source": str(markdown_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "block_count": block_index,
        "extracted_files": extracted_files,
    }


def write_extracted_artifacts(markdown_path: Path, output_dir: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    """Extract artifacts and optionally write a JSON manifest.

    Args:
        markdown_path: Source markdown file.
        output_dir: Destination directory for extracted files.
        manifest_path: Optional path for ``extract_manifest.json``.

    Returns:
        Same manifest dict returned by :func:`extract_markdown_artifacts`.
    """
    manifest = extract_markdown_artifacts(markdown_path, output_dir)
    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _filename_for_block(lang: str, body: str, block_index: int, ext: str) -> str:
    if lang == "scala":
        object_match = re.search(r"\bobject\s+([A-Za-z_][A-Za-z0-9_]*)", body)
        if object_match:
            return f"{object_match.group(1)}{ext}"
        class_match = re.search(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)", body)
        if class_match:
            return f"{class_match.group(1)}{ext}"
    if lang in {"bash", "sh", "shell"}:
        return f"build_commands_{block_index}.sh"
    if lang == "csv":
        return f"sample_data_{block_index}.csv"
    if lang == "sbt":
        return "build.sbt"
    return f"block_{block_index}{ext}"
