"""Build or validate local repo fixture snapshots."""

from __future__ import annotations

import json
import shutil
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .taxonomy import load_taxonomy, project_root


def build_fixtures(sources_path: str | Path, *, download: bool = False) -> dict[str, Any]:
    """Validate fixture directories and optionally download configured archives.

    The default mode is intentionally conservative: it creates missing lightweight
    fixture directories for local tasks and writes ``source_manifest.json`` files,
    but it does not fetch public repositories unless ``download=True`` and a source
    entry includes an explicit ``fixture_path``.
    """

    root = project_root()
    sources_path = Path(sources_path)
    sources = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or {}
    source_rows = sources.get("sources", sources if isinstance(sources, dict) else {})
    downloaded: list[str] = []
    errors: list[dict[str, str]] = []
    if download:
        for name, row in dict(source_rows).items():
            try:
                if row.get("kind") == "github_archive" and row.get("fixture_path"):
                    _download_github_archive(str(row["repo"]), root / str(row["fixture_path"]))
                    downloaded.append(str(name))
            except Exception as exc:  # noqa: BLE001
                errors.append({"source": str(name), "error": str(exc)})

    created: list[str] = []
    manifests: list[str] = []
    for task in load_taxonomy(root / "benchmark" / "taxonomy" / "tasks.yaml"):
        fixture = task.fixture_root(root)
        if not fixture.exists():
            fixture.mkdir(parents=True)
            (fixture / "README.md").write_text(
                f"# {task.title}\n\nLocal fixture placeholder for `{task.task_id}`.\n",
                encoding="utf-8",
            )
            created.append(str(fixture))
        manifest = {
            "task_id": task.task_id,
            "fixture_path": str(fixture.relative_to(root) if fixture.is_relative_to(root) else fixture),
            "source": "local_minimal_fixture",
            "generated_at": datetime.now(UTC).isoformat(),
            "downloaded": False,
            "license_preserved": any((fixture / name).exists() for name in ("LICENSE", "LICENSE.md", "COPYING")),
        }
        manifest_path = fixture / "source_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        manifests.append(str(manifest_path))

    return {
        "sources_path": str(sources_path),
        "download_requested": download,
        "downloaded_sources": downloaded,
        "created_fixtures": created,
        "manifest_paths": manifests,
        "errors": errors,
        "valid": not errors,
    }


def _download_github_archive(repo: str, destination: Path) -> None:
    """Download a GitHub default-branch archive into ``destination``."""

    url = f"https://github.com/{repo}/archive/refs/heads/master.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_zip = destination.parent / f"{repo.replace('/', '__')}.zip"
    urllib.request.urlretrieve(url, tmp_zip)  # noqa: S310 - explicit user-invoked fixture build
    tmp_extract = destination.parent / f".extract-{destination.name}"
    if tmp_extract.exists():
        shutil.rmtree(tmp_extract)
    tmp_extract.mkdir(parents=True)
    try:
        with zipfile.ZipFile(tmp_zip) as archive:
            archive.extractall(tmp_extract)
        roots = [path for path in tmp_extract.iterdir() if path.is_dir()]
        if not roots:
            raise RuntimeError(f"archive for {repo} did not contain a directory")
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(roots[0], destination, ignore=shutil.ignore_patterns(".git", "node_modules", ".venv"))
    finally:
        tmp_zip.unlink(missing_ok=True)
        shutil.rmtree(tmp_extract, ignore_errors=True)
