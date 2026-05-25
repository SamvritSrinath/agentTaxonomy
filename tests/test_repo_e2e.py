"""Optional end-to-end repo-task tests against a real git remote.

Set ``RUN_REPO_E2E=1`` to enable (requires ``git`` on PATH and network access).

Example::

    RUN_REPO_E2E=1 PYTHONPATH=src python3 -m unittest tests.test_repo_e2e -v
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from agentTaxonomy.repo_clone import git_checkout_slug, resolve_repo_for_run

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RATE_LIMITING_INSTANCE = "api_rate_limiting__repo_edit__intermediate"
REST_API_HELPER_REPO = "https://github.com/kirgudkov/rest-api-helper.git"
REST_API_HELPER_REF = "main"

# Real shell command in the cloned worktree (not the catalog fixture fake agent).
E2E_AGENT_CMD = (
    'python3 -c "from pathlib import Path; '
    "p = Path('README.md'); "
    "text = p.read_text(encoding='utf-8') if p.exists() else ''; "
    "p.write_text(text + '\\n<!-- cat-repo-e2e -->\\n', encoding='utf-8')"
    '"'
)


def _e2e_enabled() -> bool:
    return os.environ.get("RUN_REPO_E2E", "").strip().lower() in {"1", "true", "yes"}


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True, timeout=10)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


_SKIP_REASON = "Set RUN_REPO_E2E=1 and ensure git is on PATH to run real-remote repo E2E tests"


@unittest.skipUnless(_e2e_enabled() and _git_available(), _SKIP_REASON)
class RepoRemoteE2ETests(unittest.TestCase):
    """Clone and run repo tasks against https://github.com/kirgudkov/rest-api-helper."""

    def test_clone_rest_api_helper_remote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            checkout_parent = Path(tmp_dir) / "checkouts"
            resolved = resolve_repo_for_run(
                git_url=REST_API_HELPER_REPO,
                git_ref=REST_API_HELPER_REF,
                checkout_dir=checkout_parent / git_checkout_slug(REST_API_HELPER_REPO),
            )
            self.assertEqual(resolved.source_type, "git")
            self.assertTrue((resolved.path / ".git").is_dir())
            self.assertTrue((resolved.path / "package.json").is_file())
            self.assertTrue((resolved.path / "README.md").is_file())

    def test_repo_run_via_api_against_git_remote(self) -> None:
        from fastapi.testclient import TestClient

        from agentTaxonomy.db.ingest import ingest_catalog
        from agentTaxonomy.db.session import migrate_database
        from agentTaxonomy.web.api import app

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            os.environ["DATABASE_URL"] = database_url
            os.environ["CAT_ARTIFACT_ROOT"] = str(root / "artifacts")
            migrate_database(database_url)
            ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)

            client = TestClient(app)
            response = client.post(
                f"/api/instances/{RATE_LIMITING_INSTANCE}/repo-runs",
                json={
                    "git_url": REST_API_HELPER_REPO,
                    "git_ref": REST_API_HELPER_REF,
                    "execution_method": "agent",
                    "agent": "command",
                    "agent_cmd": E2E_AGENT_CMD,
                    "profile": "static",
                    "sandbox_profile": "class_b_repo_edit",
                    "output_dir": str(root / "e2e_rest_api_helper_run"),
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            job_id = response.json()["job_id"]

            job = client.get(f"/api/jobs/{job_id}")
            self.assertEqual(job.status_code, 200)
            self.assertEqual(
                job.json()["status"],
                "succeeded",
                job.json().get("error") or job.json(),
            )

            result = job.json()["result"]
            run_id = result["run_id"]
            run_dir = Path(result["run_dir"])

            run = client.get(f"/api/runs/{run_id}")
            self.assertEqual(run.status_code, 200)
            self.assertEqual(run.json()["task_mode"], "repo_task")
            self.assertEqual(run.json()["metadata_json"]["repo_source_type"], "git")
            self.assertIn("rest-api-helper", run.json()["metadata_json"].get("git_url", ""))

            request_payload = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
            self.assertEqual(request_payload["execution_method"], "agent")
            self.assertEqual(request_payload["repo_source_type"], "git")

            worktree = run_dir / "worktree"
            self.assertTrue(worktree.is_dir())
            self.assertTrue((worktree / "package.json").is_file())
            readme = (worktree / "README.md").read_text(encoding="utf-8")
            self.assertIn("cat-repo-e2e", readme)

            diff_text = (run_dir / "diff.patch").read_text(encoding="utf-8")
            self.assertIn("README.md", diff_text)
            self.assertTrue((run_dir / "trace.jsonl").exists())
            self.assertTrue((run_dir / "score.json").exists())

            artifacts = client.get(f"/api/runs/{run_id}/artifacts")
            self.assertEqual(artifacts.status_code, 200)
            by_path = {item["logical_path"]: item for item in artifacts.json()}
            self.assertIn("diff.patch", by_path)
            self.assertEqual(by_path["diff.patch"]["artifact_type"], "repo_diff")


if __name__ == "__main__":
    unittest.main()
