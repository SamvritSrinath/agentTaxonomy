from pathlib import Path
import json
import tempfile
import unittest

from agentTaxonomy.cli import _default_repo_agent_cmd, build_parser, main


class CliTests(unittest.TestCase):
    def test_build_catalog_command(self) -> None:
        exit_code = main(["build-catalog"])
        self.assertEqual(exit_code, 0)
        self.assertTrue((Path(__file__).resolve().parents[1] / "benchmark" / "generated" / "catalog.json").exists())

    def test_validate_catalog_command(self) -> None:
        exit_code = main(["validate-catalog"])
        self.assertEqual(exit_code, 0)

    def test_workbench_subcommands_are_registered(self) -> None:
        parser = build_parser()
        cases = [
            ["db", "bootstrap", "--runs-root", "runs"],
            ["db", "ingest-evaluation", "runs/demo", "--evidence-condition", "code_only"],
            ["db", "rescore-run", "run-id", "--evidence-condition", "code_plus_trace"],
            ["db", "bootstrap"],
            ["annotate", "assign", "--annotators", "samvrit,mia"],
            ["annotate", "agreement"],
            ["adjudicate", "export", "adjudications.csv"],
            ["experiment", "create", "--design", "experiments/pilot.yaml"],
            ["experiment", "run", "--design", "experiments/pilot.yaml"],
            ["experiment", "summarize", "--output", "analysis.csv"],
        ]
        for argv in cases:
            with self.subTest(argv=argv):
                self.assertIsNotNone(parser.parse_args(argv))

    def test_db_migrate_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            database_url = f"sqlite:///{Path(tmp_dir) / 'workbench.sqlite'}"
            exit_code = main(["db", "migrate", "--database-url", database_url])
            self.assertEqual(exit_code, 0)

    def test_static_audit_and_supply_chain_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            artifact = root / "agent_output.md"
            artifact.write_text("No dependencies are introduced.\n", encoding="utf-8")
            audit_output = root / "audit.json"
            supply_output = root / "supply_chain.json"

            audit_exit = main(
                [
                    "static-audit",
                    "--instance-id",
                    "cuda_reduction_kernel__expert",
                    "--artifact",
                    str(artifact),
                    "--output",
                    str(audit_output),
                ]
            )
            supply_exit = main(["enrich-supply-chain", "--artifact-dir", str(root), "--output", str(supply_output)])

            self.assertEqual(audit_exit, 0)
            self.assertEqual(supply_exit, 0)
            self.assertTrue(json.loads(audit_output.read_text(encoding="utf-8"))["security_audit_performed"])
            self.assertIn("score", json.loads(supply_output.read_text(encoding="utf-8")))

    def test_run_repo_task_cli_with_fake_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "repo_run"
            exit_code = main(
                [
                    "run-repo-task",
                    "--instance-id",
                    "api_rate_limiting__repo_edit__intermediate",
                    "--repo",
                    "benchmark/repo_fixtures/api_rate_limiting",
                    "--agent-cmd",
                    "python scripts/fake_repo_agent.py --mode good --worktree {worktree}",
                    "--profile",
                    "smoke",
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "prompt.md").exists())
            self.assertTrue(json.loads((output_dir / "tests.json").read_text(encoding="utf-8"))["passed"])
            self.assertTrue(json.loads((output_dir / "oracle_results.json").read_text(encoding="utf-8"))["passed"])

    def test_default_opencode_agent_cmd_uses_current_cli_flags(self) -> None:
        cmd = _default_repo_agent_cmd("opencode")
        assert cmd is not None
        self.assertIn("--dir {worktree}", cmd)
        self.assertIn("-f {prompt_file}", cmd)
        self.assertNotIn("--cwd", cmd)
        self.assertNotIn("--prompt-file", cmd)


if __name__ == "__main__":
    unittest.main()
