import os
import shutil
import tempfile
import unittest
from pathlib import Path

from agentTaxonomy.db.exports import export_evaluations, export_wide
from agentTaxonomy.db.ingest import (
    IngestConflict,
    ingest_catalog,
    ingest_evaluation,
    ingest_run,
    rescore_run,
    sha256_text,
    upsert_artifact_revision,
)
from agentTaxonomy.db.models import (
    ArtifactRecord,
    ArtifactVersionRecord,
    EvaluationRecord,
    FindingRecord,
    PromptVariantRecord,
    RunRecord,
)
from agentTaxonomy.db.services import (
    assign_annotations,
    compute_annotation_agreement,
    create_adjudication,
    create_annotation,
    get_artifact_content,
    list_repo_targets_for_instance,
    resolve_repo_binding,
    selected_text_matches,
    update_annotation_status,
)
from agentTaxonomy.db.bootstrap import run_bootstrap
from agentTaxonomy.db.models import PromptVariantRecord
from agentTaxonomy.db.session import migrate_database, reset_database, session_scope
from sqlalchemy import func, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class WorkbenchDbTests(unittest.TestCase):
    def test_ingest_run_idempotency_conflict_and_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            import os

            os.environ["CAT_ARTIFACT_ROOT"] = str(root / "artifacts")
            run_dir = root / "run"
            shutil.copytree(PROJECT_ROOT / "runs" / "map_reduce_spark_log_analytics" / "beginner_gpt55", run_dir)
            reset_database(database_url)

            catalog = ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)
            first = ingest_run(run_dir, database_url=database_url, artifact_root=root / "artifacts")
            second = ingest_run(run_dir, database_url=database_url, artifact_root=root / "artifacts")

            self.assertEqual(catalog.status, "updated")
            self.assertEqual(first.status, "created")
            self.assertEqual(second.status, "noop")
            self.assertEqual(first.record_id, second.record_id)

            (run_dir / "agent_output.md").write_text("changed\n", encoding="utf-8")
            with self.assertRaises(IngestConflict):
                ingest_run(run_dir, database_url=database_url, artifact_root=root / "artifacts")
            changed = ingest_run(
                run_dir,
                database_url=database_url,
                artifact_root=root / "artifacts",
                new_ingest_version=True,
            )
            self.assertEqual(changed.status, "updated")
            self.assertEqual(changed.ingest_version, 2)
            self.assertEqual(changed.record_id, first.record_id)
            with session_scope(database_url) as session:
                self.assertEqual(session.scalars(select(RunRecord)).all().__len__(), 1)

            export_evaluations(root / "evaluations.csv", database_url=database_url)
            export_wide(root / "analysis.csv", database_url=database_url)
            self.assertIn("evaluation_inputs", (root / "evaluations.csv").read_text(encoding="utf-8"))
            analysis_text = (root / "analysis.csv").read_text(encoding="utf-8")
            self.assertIn("security_adjusted_success", analysis_text)
            self.assertIn("human_security_verdict", analysis_text)

            with session_scope(database_url) as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(RunRecord)), 1)
                self.assertEqual(session.scalar(select(func.count()).select_from(EvaluationRecord)), 1)

    def test_explicit_evaluations_have_distinct_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            import os

            os.environ["CAT_ARTIFACT_ROOT"] = str(root / "artifacts")
            run_dir = root / "run"
            shutil.copytree(PROJECT_ROOT / "runs" / "map_reduce_spark_log_analytics" / "beginner_gpt55", run_dir)
            reset_database(database_url)
            ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)
            result = ingest_run(run_dir, database_url=database_url, artifact_root=root / "artifacts")
            code_only = ingest_evaluation(run_dir, evidence_condition="code_only", database_url=database_url)
            code_plus_trace = rescore_run(result.record_id, evidence_condition="code_plus_trace", database_url=database_url)

            with session_scope(database_url) as session:
                evaluations = session.scalars(
                    select(EvaluationRecord).where(EvaluationRecord.id.in_([code_only.record_id, code_plus_trace.record_id]))
                ).all()
                by_condition = {item.evidence_condition: item for item in evaluations}
                self.assertFalse(by_condition["code_only"].evaluation_inputs["included_sources"]["trace"])
                self.assertTrue(by_condition["code_plus_trace"].evaluation_inputs["included_sources"]["trace"])

    def test_artifact_revisions_annotations_and_text_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            import os

            os.environ["CAT_ARTIFACT_ROOT"] = str(root / "artifacts")
            run_dir = root / "run"
            shutil.copytree(PROJECT_ROOT / "runs" / "map_reduce_spark_log_analytics" / "beginner_gpt55", run_dir)
            reset_database(database_url)
            ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)
            result = ingest_run(run_dir, database_url=database_url, artifact_root=root / "artifacts")

            with session_scope(database_url) as session:
                artifact = session.scalar(select(ArtifactRecord).where(ArtifactRecord.logical_path == "agent_output.md"))
                assert artifact is not None
                content = get_artifact_content(session, artifact.id)
                assert content is not None
                self.assertEqual(content["logical_path"], "agent_output.md")
                upsert_artifact_revision(
                    session,
                    run_id=result.record_id,
                    logical_path="agent_output.md",
                    artifact_type="run_artifact",
                    content_hash="0" * 64,
                    storage_path=str(root / "artifacts" / "changed"),
                    size_bytes=7,
                    mime_type="text/markdown",
                    source_file=str(run_dir / "agent_output.md"),
                    source_file_hash="0" * 64,
                    ingest_version="ingest.v2",
                )
                self.assertEqual(
                    session.scalar(
                        select(func.count()).select_from(ArtifactVersionRecord).where(
                            ArtifactVersionRecord.artifact_id == artifact.id
                        )
                    ),
                    2,
                )

                run_annotation = create_annotation(
                    session,
                    {
                        "run_id": result.record_id,
                        "annotator": "samvrit",
                        "label": "correct_but_insecure",
                        "rationale": "The run has a security-relevant failure.",
                        "selected_text": "evidence",
                    },
                )
                finding_id = session.scalar(select(FindingRecord.id).limit(1))
                finding_annotation = create_annotation(
                    session,
                    {
                        "run_id": result.record_id,
                        "finding_id": finding_id,
                        "annotator": "mia",
                        "label": "other",
                        "rationale": "Second annotation for workflow coverage.",
                        "queue_status": "assigned",
                    },
                )
                updated = update_annotation_status(session, str(finding_annotation["id"]), "in_progress")

                self.assertEqual(run_annotation["annotation_scope"], "run")
                self.assertEqual(finding_annotation["annotation_scope"], "finding")
                self.assertEqual(updated["queue_status"], "in_progress")
                self.assertTrue(selected_text_matches(selected_text="evidence", selected_text_hash=sha256_text("evidence")))
                self.assertFalse(selected_text_matches(selected_text="changed", selected_text_hash=sha256_text("evidence")))
                self.assertIsNotNone(finding_id)

    def test_stale_artifact_span_rejected_and_adjudication_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            import os

            os.environ["CAT_ARTIFACT_ROOT"] = str(root / "artifacts")
            run_dir = root / "run"
            shutil.copytree(PROJECT_ROOT / "runs" / "map_reduce_spark_log_analytics" / "beginner_gpt55", run_dir)
            reset_database(database_url)
            ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)
            result = ingest_run(run_dir, database_url=database_url, artifact_root=root / "artifacts")

            with session_scope(database_url) as session:
                artifact = session.scalar(select(ArtifactRecord).where(ArtifactRecord.logical_path == "agent_output.md"))
                assert artifact is not None
                with self.assertRaises(ValueError):
                    create_annotation(
                        session,
                        {
                            "run_id": result.record_id,
                            "annotator": "samvrit",
                            "label": "correct_but_insecure",
                            "rationale": "stale evidence",
                            "artifact_id": artifact.id,
                            "file_path": artifact.logical_path,
                            "start_line": 1,
                            "end_line": 1,
                            "selected_text_hash": "0" * 64,
                        },
                    )
                assigned = assign_annotations(session, annotators=["samvrit", "mia"], run_ids=[result.record_id])
                self.assertEqual(len(assigned), 2)
                create_annotation(
                    session,
                    {
                        "run_id": result.record_id,
                        "annotator": "samvrit",
                        "label": "correctness_failure",
                        "correctness_verdict": "fail",
                        "security_verdict": "unknown",
                        "rationale": "does not work",
                    },
                )
                create_annotation(
                    session,
                    {
                        "run_id": result.record_id,
                        "annotator": "mia",
                        "label": "functional_but_insecure",
                        "correctness_verdict": "pass",
                        "security_verdict": "fail",
                        "rationale": "security issue",
                    },
                )
                agreement = compute_annotation_agreement(session)
                self.assertEqual(agreement["disagreements"], 1)
                adjudication = create_adjudication(
                    session,
                    {
                        "run_id": result.record_id,
                        "final_label": "functional_but_insecure",
                        "adjudicator": "lead",
                        "rationale": "final decision",
                    },
                )
                self.assertEqual(adjudication["final_label"], "functional_but_insecure")

    def test_export_wide_joins_run_level_annotation_on_each_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            import os

            os.environ["CAT_ARTIFACT_ROOT"] = str(root / "artifacts")
            run_dir = root / "run"
            shutil.copytree(PROJECT_ROOT / "runs" / "map_reduce_spark_log_analytics" / "beginner_gpt55", run_dir)
            reset_database(database_url)
            ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)
            result = ingest_run(run_dir, database_url=database_url, artifact_root=root / "artifacts")
            rescore_run(result.record_id, evidence_condition="code_plus_trace", database_url=database_url)
            with session_scope(database_url) as session:
                create_annotation(
                    session,
                    {
                        "run_id": result.record_id,
                        "annotator": "samvrit",
                        "label": "correct_but_insecure",
                        "rationale": "run-level export join",
                        "correctness_verdict": "pass",
                        "security_verdict": "fail",
                        "queue_status": "submitted",
                    },
                )
            export_wide(root / "analysis.csv", database_url=database_url)
            lines = (root / "analysis.csv").read_text(encoding="utf-8").strip().splitlines()[1:]
            self.assertGreaterEqual(len(lines), 2)
            for line in lines:
                self.assertIn("fail", line)


    def test_ingest_run_propagates_task_mode_from_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            os.environ["CAT_ARTIFACT_ROOT"] = str(root / "artifacts")
            migrate_database(database_url)
            ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)
            run_dir = root / "trace_only_run"
            shutil.copytree(PROJECT_ROOT / "runs" / "map_reduce_spark_log_analytics" / "beginner_gpt55", run_dir)
            (run_dir / "score.json").unlink()
            result = ingest_run(run_dir, database_url=database_url, artifact_root=root / "artifacts")
            with session_scope(database_url) as session:
                run = session.get(RunRecord, result.record_id)
                assert run is not None
                self.assertEqual(run.instance_id, "map_reduce_spark_log_analytics__beginner")
                self.assertEqual(run.task_mode, "generative_task")

    def test_bootstrap_prunes_catalog_shadow_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            database_url = f"sqlite:///{Path(tmp_dir) / 'workbench.sqlite'}"
            migrate_database(database_url)
            ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)
            with session_scope(database_url) as session:
                session.add(
                    PromptVariantRecord(
                        instance_id="map_reduce_spark_log_analytics__beginner",
                        variant_name="canonical",
                        skill_level="beginner",
                        prompt_style="canonical",
                        prompt_text="shadow",
                    )
                )
            run_bootstrap(database_url=database_url)
            with session_scope(database_url) as session:
                rows = session.scalars(select(PromptVariantRecord)).all()
            for row in rows:
                self.assertNotEqual(row.variant_name, "canonical")
                self.assertNotEqual(row.variant_name, row.instance_id)

    def test_prompt_services(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            migrate_database(database_url)
            ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)
            from agentTaxonomy.db.services import (
                create_prompt,
                duplicate_prompt,
                get_prompt,
                list_prompt_templates,
                list_prompts,
                update_prompt,
            )

            with session_scope(database_url) as session:
                instance_id = "map_reduce_spark_log_analytics__beginner"
                created = create_prompt(
                    session,
                    {
                        "instance_id": instance_id,
                        "variant_name": "custom_test",
                        "prompt_text": "Custom prompt body",
                    },
                )
                prompt_id = created["id"]
                listed = list_prompts(session, instance_id=instance_id)
                self.assertTrue(any(item["id"] == prompt_id for item in listed))
                updated = update_prompt(session, prompt_id, {"prompt_text": "Updated body"})
                self.assertEqual(updated["prompt_text"], "Updated body")
                copy = duplicate_prompt(session, prompt_id)
                self.assertNotEqual(copy["id"], prompt_id)
                fetched = get_prompt(session, prompt_id)
                assert fetched is not None
                templates = list_prompt_templates(session)
                self.assertIsInstance(templates, list)

    def test_catalog_ingest_creates_default_repo_target_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            database_url = f"sqlite:///{Path(tmp_dir) / 'workbench.sqlite'}"
            reset_database(database_url)
            ingest_catalog(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json", database_url=database_url)
            instance_id = "flask_mvc_refactor__repo_edit__intermediate"
            with session_scope(database_url) as session:
                targets = list_repo_targets_for_instance(session, instance_id)
                self.assertGreaterEqual(len(targets), 1)
                default = next(item for item in targets if item.get("binding", {}).get("is_default"))
                self.assertEqual(default["source_type"], "local_fixture")
                self.assertEqual(default["repo_path"], "benchmark/repo_fixtures/flask_mvc_refactor")
                target, binding = resolve_repo_binding(session, instance_id)
                assert binding is not None
                self.assertEqual(target.id, default["id"])
                self.assertIn("app.py", binding.allowed_output_files)
                self.assertIn("oracle/**", binding.protected_files)


if __name__ == "__main__":
    unittest.main()
