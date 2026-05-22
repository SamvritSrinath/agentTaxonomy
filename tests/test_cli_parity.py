"""CLI parity gate: existing catt workflows must pass before UI work."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentTaxonomy.cli import main, main_deprecated
from agentTaxonomy.db import ingest_catalog, ingest_run, migrate_database, reset_database
from agentTaxonomy.generate import OpenRouterGenerationConfig, generate_run
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeGenerator:
    def _build_request(self, prompt: str, system_prompt: str):
        return {
            "model": "moonshotai/kimi-k2.5",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        }

    def generate(self, prompt: str, system_prompt: str):
        return {"choices": [{"message": {"content": "Generated solution.\n"}}]}


class CliParityTests(unittest.TestCase):
    def test_build_catalog_command(self) -> None:
        exit_code = main(["build-catalog"])
        self.assertEqual(exit_code, 0)
        catalog = json.loads((PROJECT_ROOT / "benchmark" / "generated" / "catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["benchmark_name"], "coding-agent-taxonomy")

    def test_uab_deprecated_alias_still_exits_zero(self) -> None:
        exit_code = main_deprecated(["validate-catalog"])
        self.assertEqual(exit_code, 0)

    def test_validate_catalog_command(self) -> None:
        exit_code = main(["validate-catalog"])
        self.assertEqual(exit_code, 0)

    def test_generate_run_with_mocked_openrouter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            prompt_file = root / "beginner.md"
            output_dir = root / "run"
            prompt_file.write_text("Implement a Spark log analytics program.", encoding="utf-8")

            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test"}, clear=False):
                with patch("agentTaxonomy.generate.OpenRouterGenerator.generate", return_value={"choices": [{"message": {"content": "Generated solution.\n"}}]}):
                    exit_code = main(
                        [
                            "generate-run",
                            "--prompt-file",
                            str(prompt_file),
                            "--model",
                            "moonshotai/kimi-k2.5",
                            "--output-dir",
                            str(output_dir),
                            "--instance-id",
                            "map_reduce_spark_log_analytics__beginner",
                        ]
                    )
            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "agent_output.md").exists())
            self.assertTrue((output_dir / "trace.jsonl").exists())

    def test_extract_static_supply_score_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            prompt_file = root / "expert.md"
            output_dir = root / "run"
            prompt_file.write_text("Implement a CUDA reduction kernel.", encoding="utf-8")
            generate_run(
                prompt_file=prompt_file,
                output_dir=output_dir,
                config=OpenRouterGenerationConfig(api_key="test", model="moonshotai/kimi-k2.5"),
                instance_id="cuda_reduction_kernel__expert",
                generator=FakeGenerator(),
            )

            extract_exit = main(
                [
                    "extract-artifacts",
                    "--artifact",
                    str(output_dir / "agent_output.md"),
                    "--output-dir",
                    str(output_dir / "extracted"),
                ]
            )
            audit_exit = main(
                [
                    "static-audit",
                    "--instance-id",
                    "cuda_reduction_kernel__expert",
                    "--artifact-dir",
                    str(output_dir / "extracted"),
                    "--output",
                    str(output_dir / "audit.json"),
                ]
            )
            supply_exit = main(
                [
                    "enrich-supply-chain",
                    "--artifact-dir",
                    str(output_dir / "extracted"),
                    "--output",
                    str(output_dir / "supply_chain.json"),
                ]
            )
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test"}, clear=False):
                score_exit = main(
                    [
                        "score-run",
                        "--instance-id",
                        "cuda_reduction_kernel__expert",
                        "--trace",
                        str(output_dir / "trace.jsonl"),
                        "--verification-tier",
                        "static",
                        "--audit-report",
                        str(output_dir / "audit.json"),
                        "--supply-chain-report",
                        str(output_dir / "supply_chain.json"),
                        "--full-execution-skipped",
                        "--skip-reason",
                        "cli parity test",
                        "--output",
                        str(output_dir / "score.json"),
                    ]
                )

            self.assertEqual(extract_exit, 0)
            self.assertEqual(audit_exit, 0)
            self.assertEqual(supply_exit, 0)
            self.assertEqual(score_exit, 0)
            score_path = output_dir / "score.json"
            self.assertTrue(score_path.exists())
            payload = json.loads(score_path.read_text(encoding="utf-8"))
            self.assertIn("utility_score", payload)
            self.assertIn("security_adjusted_success", payload)

    def test_db_ingest_catalog_and_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            migrate_database(database_url)
            reset_database(database_url)

            catalog_exit = main(
                ["db", "ingest-catalog", str(PROJECT_ROOT / "benchmark" / "generated" / "catalog.json"), "--database-url", database_url]
            )
            self.assertEqual(catalog_exit, 0)

            run_dir = PROJECT_ROOT / "runs" / "map_reduce_spark_log_analytics" / "beginner_gpt55"
            ingest_exit = main(["db", "ingest-run", str(run_dir), "--database-url", database_url])
            self.assertEqual(ingest_exit, 0)

            result = ingest_run(run_dir, database_url=database_url, artifact_root=root / "artifacts")
            self.assertEqual(result.status, "noop")


if __name__ == "__main__":
    unittest.main()
