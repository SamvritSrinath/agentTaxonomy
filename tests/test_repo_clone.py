"""Tests for git clone resolution used by repo-task runs."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from agentTaxonomy.repo_clone import (
    clone_git_repo,
    external_checkouts_root,
    git_checkout_slug,
    resolve_repo_for_run,
)


class RepoCloneTests(unittest.TestCase):
    def test_git_checkout_slug(self) -> None:
        self.assertEqual(git_checkout_slug("git@github.com:acme/widget.git"), "acme__widget")
        self.assertEqual(git_checkout_slug("https://github.com/acme/widget"), "acme__widget")

    def test_clone_local_git_repo_into_external_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bare = root / "bare.git"
            checkout = root / "source"
            checkout.mkdir()
            (checkout / "app.py").write_text("x = 1\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=checkout, check=True, capture_output=True)
            subprocess.run(["git", "add", "app.py"], cwd=checkout, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "init", "--author", "test <test@example.com>"],
                cwd=checkout,
                check=True,
                capture_output=True,
                env={"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com", **__import__("os").environ},
            )
            subprocess.run(["git", "clone", "--bare", str(checkout), str(bare)], check=True, capture_output=True)

            external_root = root / "_external"
            cloned = clone_git_repo(f"file://{bare}", checkout_dir=external_root / "demo__repo")
            self.assertTrue((cloned / "app.py").exists())
            self.assertTrue((cloned / ".git").exists())

            resolved = resolve_repo_for_run(git_url=f"file://{bare}", checkout_dir=external_root / "via_resolver")
            self.assertEqual(resolved.source_type, "git")
            self.assertTrue(resolved.path.is_dir())

    def test_resolve_local_path_relative_to_project(self) -> None:
        resolved = resolve_repo_for_run(repo_path=Path("benchmark/repo_fixtures/api_rate_limiting"))
        self.assertEqual(resolved.source_type, "local_path")
        self.assertTrue(resolved.path.name == "api_rate_limiting")

    def test_reuse_existing_checkout_with_refresh_passes_cwd(self) -> None:
        """Regression: _git() requires cwd= keyword; refresh must not pass Path as first arg."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bare = root / "bare.git"
            checkout = root / "source"
            checkout.mkdir()
            (checkout / "app.py").write_text("x = 1\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=checkout, check=True, capture_output=True)
            subprocess.run(["git", "add", "app.py"], cwd=checkout, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "init", "--author", "test <test@example.com>"],
                cwd=checkout,
                check=True,
                capture_output=True,
                env={"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com", **__import__("os").environ},
            )
            subprocess.run(["git", "clone", "--bare", str(checkout), str(bare)], check=True, capture_output=True)

            dest = root / "reuse_me"
            clone_git_repo(f"file://{bare}", checkout_dir=dest)
            resolved = resolve_repo_for_run(
                git_url=f"file://{bare}",
                checkout_dir=dest,
                refresh_clone=True,
            )
            self.assertEqual(resolved.path.resolve(), dest.resolve())


if __name__ == "__main__":
    unittest.main()
