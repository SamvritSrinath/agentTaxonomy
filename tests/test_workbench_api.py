import os
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agentTaxonomy.db.ingest import ingest_catalog, ingest_run
from agentTaxonomy.db.models import ArtifactRecord, BenchmarkInstanceRecord
from agentTaxonomy.db.session import migrate_database, reset_database, session_scope
from agentTaxonomy.web.api import app
from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class WorkbenchApiTests(unittest.TestCase):
    def test_artifact_content_and_stale_annotation_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            os.environ["DATABASE_URL"] = database_url
            os.environ["CAT_ARTIFACT_ROOT"] = str(root / "artifacts")
            run_dir = root / "run"
            shutil.copytree(PROJECT_ROOT / "runs" / "map_reduce_spark_log_analytics" / "beginner_gpt55", run_dir)
            reset_database(database_url)
            ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)
            result = ingest_run(run_dir, database_url=database_url, artifact_root=root / "artifacts")

            with session_scope(database_url) as session:
                artifact = session.scalar(select(ArtifactRecord).where(ArtifactRecord.logical_path == "agent_output.md"))
                assert artifact is not None
                artifact_id = artifact.id

            client = TestClient(app)
            content = client.get(f"/api/artifacts/{artifact_id}/content")
            self.assertEqual(content.status_code, 200)
            self.assertEqual(content.json()["logical_path"], "agent_output.md")

            stale = client.post(
                f"/api/runs/{result.record_id}/annotations",
                json={
                    "run_id": result.record_id,
                    "annotator": "samvrit",
                    "label": "correct_but_insecure",
                    "rationale": "stale",
                    "artifact_id": artifact_id,
                    "file_path": "agent_output.md",
                    "start_line": 1,
                    "end_line": 1,
                    "selected_text_hash": "0" * 64,
                },
            )
            self.assertEqual(stale.status_code, 400)

            rescore = client.post(
                "/api/evaluations/rescore",
                json={"run_id": result.record_id, "evidence_condition": "code_only"},
            )
            self.assertEqual(rescore.status_code, 200)
            self.assertIn("job_id", rescore.json())

            scores = client.get(f"/api/runs/{result.record_id}/scores")
            self.assertEqual(scores.status_code, 200)
            self.assertIn("canonical_evaluation_id", scores.json())

            judge = client.post(
                f"/api/runs/{result.record_id}/judge-pipeline",
                json={"evidence_condition": "code_only", "verification_tier": "static"},
            )
            self.assertEqual(judge.status_code, 200)
            self.assertIn("job_id", judge.json())
            job = client.get(f"/api/jobs/{judge.json()['job_id']}")
            self.assertEqual(job.status_code, 200)
            self.assertEqual(job.json()["metadata_json"]["evidence_condition"], "code_only")

            instance = client.get("/api/instances/map_reduce_spark_log_analytics__beginner")
            self.assertEqual(instance.status_code, 200)
            self.assertIn("agent_prompt", instance.json())

            annotation = client.post(
                f"/api/runs/{result.record_id}/annotations",
                json={
                    "run_id": result.record_id,
                    "annotator": "samvrit",
                    "label": "correct_but_insecure",
                    "rationale": "run-level only",
                    "evaluation_id": "ignored-should-not-bind",
                },
            )
            self.assertEqual(annotation.status_code, 200)
            self.assertIsNone(annotation.json().get("evaluation_id"))

            listed = client.get(f"/api/runs/{result.record_id}/annotations")
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(len(listed.json()), 1)
            self.assertEqual(listed.json()[0]["label"], "correct_but_insecure")

    def test_bootstrap_and_jobs_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            os.environ["DATABASE_URL"] = database_url
            migrate_database(database_url)
            client = TestClient(app)
            bootstrap = client.post("/api/bootstrap", json={"rebuild_catalog": False, "runs_root": str(root / "runs")})
            self.assertEqual(bootstrap.status_code, 200)
            job_id = bootstrap.json()["job_id"]
            job = client.get(f"/api/jobs/{job_id}")
            self.assertEqual(job.status_code, 200)
            self.assertIn(job.json()["status"], {"queued", "running", "succeeded", "failed"})

    def test_generate_rejects_repo_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            os.environ["DATABASE_URL"] = database_url
            migrate_database(database_url)
            ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)
            with session_scope(database_url) as session:
                repo_instance = session.scalar(
                    select(BenchmarkInstanceRecord)
                    .where(BenchmarkInstanceRecord.task_mode == "repo_task")
                    .limit(1)
                )
                assert repo_instance is not None
                instance_id = repo_instance.instance_id
            client = TestClient(app)
            response = client.post(
                f"/api/instances/{instance_id}/generate",
                json={"model": "moonshotai/kimi-k2.5"},
            )
            self.assertEqual(response.status_code, 400)
            body = response.json()
            self.assertEqual(body["detail"]["error"], "repo_task_generate_not_supported_in_ui")

    def test_openrouter_usage_endpoint_mocked(self) -> None:
        from unittest.mock import patch

        client = TestClient(app)
        payload = {
            "key": {"data": {"usage_daily": 1.5, "usage_monthly": 12.0, "label": "test"}},
            "fetched_at": "2026-01-01T00:00:00+00:00",
        }
        with patch("agentTaxonomy.web.api.fetch_usage", return_value=payload):
            with patch("agentTaxonomy.web.api.resolve_api_key", return_value="test-key"):
                response = client.get("/api/openrouter/usage")
        self.assertEqual(response.status_code, 200)
        self.assertIn("key", response.json())
        self.assertIn("fetched_at", response.json())

    def test_generate_from_prompt_variant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            os.environ["DATABASE_URL"] = database_url
            migrate_database(database_url)
            ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)
            client = TestClient(app)
            created = client.post(
                "/api/prompts",
                json={
                    "instance_id": "map_reduce_spark_log_analytics__beginner",
                    "variant_name": "ui_test",
                    "prompt_text": "Generate from this specific prompt variant.",
                },
            )
            self.assertEqual(created.status_code, 200)
            prompt_id = created.json()["id"]
            response = client.post(
                f"/api/prompts/{prompt_id}/generate",
                json={"model": "moonshotai/kimi-k2.5"},
            )
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["prompt_id"], prompt_id)
            self.assertIn("job_id", body)

    def test_prompt_and_jobs_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            os.environ["DATABASE_URL"] = database_url
            migrate_database(database_url)
            ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)
            client = TestClient(app)
            prompts = client.get("/api/prompts")
            self.assertEqual(prompts.status_code, 200)
            templates = client.get("/api/prompt-templates")
            self.assertEqual(templates.status_code, 200)
            jobs = client.get("/api/jobs")
            self.assertEqual(jobs.status_code, 200)
            self.assertIsInstance(jobs.json(), list)


if __name__ == "__main__":
    unittest.main()
