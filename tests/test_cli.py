from pathlib import Path
import json
import tempfile
import unittest

from agentTaxonomy.cli import main


class CliTests(unittest.TestCase):
    def test_build_catalog_command(self) -> None:
        exit_code = main(["build-catalog"])
        self.assertEqual(exit_code, 0)
        self.assertTrue((Path(__file__).resolve().parents[1] / "benchmark" / "generated" / "catalog.json").exists())

    def test_validate_catalog_command(self) -> None:
        exit_code = main(["validate-catalog"])
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
