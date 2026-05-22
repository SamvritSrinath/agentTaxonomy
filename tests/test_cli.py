from pathlib import Path
import json
import tempfile
import unittest

from agentTaxonomy.cli import build_parser, main


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


if __name__ == "__main__":
    unittest.main()
