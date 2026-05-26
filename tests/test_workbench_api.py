import os
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agentTaxonomy.db.jobs import create_job, run_job_in_background
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
            self.assertEqual(job.json()["kind"], "judge")
            self.assertEqual(job.json()["metadata_json"]["evidence_condition"], "code_only")
            self.assertEqual(job.json()["metadata_json"]["run_id"], result.record_id)
            listed_kinds = {row["kind"] for row in client.get("/api/jobs").json()}
            self.assertIn("judge", listed_kinds)

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

    def test_failed_job_exposes_traceback_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            database_url = f"sqlite:///{Path(tmp_dir) / 'workbench.sqlite'}"
            os.environ["DATABASE_URL"] = database_url
            migrate_database(database_url)
            with session_scope(database_url) as session:
                job_id = create_job(session, kind="ingest", metadata={"run_dir": "missing"})["id"]

            def worker(_job_id: str) -> None:
                raise RuntimeError("boom")

            run_job_in_background(job_id, worker, database_url=database_url)
            client = TestClient(app)
            job = client.get(f"/api/jobs/{job_id}")
            self.assertEqual(job.status_code, 200)
            self.assertEqual(job.json()["status"], "failed")
            self.assertTrue(job.json()["has_traceback"])
            self.assertNotIn("traceback", job.json()["metadata_json"])
            traceback_response = client.get(f"/api/jobs/{job_id}/traceback")
            self.assertEqual(traceback_response.status_code, 200)
            self.assertIn("RuntimeError: boom", traceback_response.text)

    def test_failed_job_traceback_endpoint_falls_back_to_error_details(self) -> None:
        from agentTaxonomy.db.jobs import update_job

        with tempfile.TemporaryDirectory() as tmp_dir:
            database_url = f"sqlite:///{Path(tmp_dir) / 'workbench.sqlite'}"
            os.environ["DATABASE_URL"] = database_url
            migrate_database(database_url)
            with session_scope(database_url) as session:
                job_id = create_job(session, kind="repo_run", metadata={"instance_id": "database_operations__expert"})[
                    "id"
                ]
                update_job(session, job_id, status="failed", phase="openrouter", error="not_allowed:cleanup.py")

            client = TestClient(app)
            response = client.get(f"/api/jobs/{job_id}/traceback")
            self.assertEqual(response.status_code, 200)
            self.assertIn("No Python traceback was captured", response.text)
            self.assertIn("not_allowed:cleanup.py", response.text)
            self.assertIn("database_operations__expert", response.text)

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
            self.assertIn("repo-runs", response.text)

    def test_repo_run_model_execution_method(self) -> None:
        from unittest.mock import patch

        stub_response = {
            "choices": [
                {
                    "message": {
                        "content": "```app.py\n# patched by stub model\n```\n",
                    }
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            os.environ["DATABASE_URL"] = database_url
            os.environ["OPENROUTER_API_KEY"] = "test-key"
            os.environ["CAT_ARTIFACT_ROOT"] = str(root / "artifacts")
            migrate_database(database_url)
            ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)
            client = TestClient(app)
            with patch("agentTaxonomy.agents.openrouter_repo_agent.OpenRouterGenerator._send_request", return_value=stub_response):
                response = client.post(
                    "/api/instances/api_rate_limiting__repo_edit__intermediate/repo-runs",
                    json={
                        "execution_method": "model",
                        "model": "stub/model",
                        "profile": "static",
                        "output_dir": str(root / "repo_model_run"),
                    },
                )
            self.assertEqual(response.status_code, 200, response.text)
            job = client.get(f"/api/jobs/{response.json()['job_id']}")
            self.assertEqual(job.status_code, 200)
            self.assertEqual(job.json()["status"], "succeeded", job.json().get("error"))
            self.assertEqual(job.json()["kind"], "repo_run")
            run_id = job.json()["result"]["run_id"]
            self.assertEqual(job.json()["metadata_json"]["run_id"], run_id)
            listed = client.get("/api/jobs")
            self.assertEqual(listed.status_code, 200)
            listed_job = next(row for row in listed.json() if row["id"] == job.json()["id"])
            self.assertEqual(listed_job["result"]["run_id"], run_id)
            self.assertEqual(listed_job["metadata_json"]["execution_method"], "model")
            run = client.get(f"/api/runs/{run_id}")
            self.assertEqual(run.status_code, 200)
            self.assertEqual(run.json()["task_mode"], "repo_task")
            run_dir = Path(job.json()["result"]["run_dir"])
            self.assertTrue((run_dir / "worktree").exists())
            self.assertTrue((run_dir / "agent_output.md").exists())
            self.assertTrue((run_dir / "raw_response.json").exists())
            self.assertTrue((run_dir / "diff.patch").exists())

    def test_repo_run_endpoint_uses_fake_agent_and_indexes_repo_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            os.environ["DATABASE_URL"] = database_url
            os.environ["CAT_ARTIFACT_ROOT"] = str(root / "artifacts")
            migrate_database(database_url)
            ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)
            client = TestClient(app)

            targets = client.get("/api/instances/api_rate_limiting__repo_edit__intermediate/repo-targets")
            self.assertEqual(targets.status_code, 200)
            self.assertTrue(any(item.get("binding", {}).get("is_default") for item in targets.json()))

            response = client.post(
                "/api/instances/api_rate_limiting__repo_edit__intermediate/repo-runs",
                json={
                    "agent": "command",
                    "agent_cmd": "python scripts/fake_repo_agent.py --mode good --worktree {worktree}",
                    "profile": "smoke",
                    "sandbox_profile": "class_b_repo_edit",
                    "output_dir": str(root / "repo_run"),
                },
            )
            self.assertEqual(response.status_code, 200)
            job = client.get(f"/api/jobs/{response.json()['job_id']}")
            self.assertEqual(job.status_code, 200)
            self.assertEqual(job.json()["status"], "succeeded", job.json().get("error"))
            run_id = job.json()["result"]["run_id"]

            run = client.get(f"/api/runs/{run_id}")
            self.assertEqual(run.status_code, 200)
            self.assertEqual(run.json()["task_mode"], "repo_task")
            self.assertEqual(run.json()["metadata_json"]["repo_source_type"], "local_fixture")

            artifacts = client.get(f"/api/runs/{run_id}/artifacts")
            self.assertEqual(artifacts.status_code, 200)
            by_path = {item["logical_path"]: item for item in artifacts.json()}
            self.assertEqual(by_path["diff.patch"]["artifact_type"], "repo_diff")
            self.assertEqual(by_path["scope_report.json"]["artifact_type"], "repo_scope")
            self.assertEqual(by_path["tests.json"]["artifact_type"], "repo_tests")
            self.assertEqual(by_path["oracle_results.json"]["artifact_type"], "repo_oracles")

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
