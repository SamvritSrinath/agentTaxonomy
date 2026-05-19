from pathlib import Path
import tempfile
import unittest

from agentTaxonomy.supply_chain import enrich_supply_chain


class SupplyChainTests(unittest.TestCase):
    def test_enrichment_extracts_manifests_and_blocks_risks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "package.json").write_text(
                '{"dependencies": {"left-pad": "^1.3.0", "safe": "1.0.0"}}',
                encoding="utf-8",
            )
            (root / "requirements.txt").write_text("fastapi>=0.100\npytest==8.0.0\n", encoding="utf-8")
            (root / "Dockerfile").write_text("FROM python:latest\n", encoding="utf-8")
            workflow = root / ".github" / "workflows"
            workflow.mkdir(parents=True)
            (workflow / "ci.yml").write_text("steps:\n  - uses: actions/checkout@main\n", encoding="utf-8")

            report = enrich_supply_chain(root)

            self.assertTrue(report["blocking"])
            self.assertEqual(report["score"], 0.0)
            self.assertGreaterEqual(report["summary"]["manifest_count"], 4)
            finding_ids = {finding["id"] for finding in report["findings"]}
            self.assertIn("unpinned_npm_dependency", finding_ids)
            self.assertIn("unpinned_python_dependency", finding_ids)
            self.assertIn("unpinned_docker_base", finding_ids)
            self.assertIn("floating_github_action", finding_ids)

    def test_enrichment_passes_without_manifests_or_install_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("No dependencies are introduced.\n", encoding="utf-8")

            report = enrich_supply_chain(root)

            self.assertFalse(report["blocking"])
            self.assertEqual(report["score"], 1.0)


if __name__ == "__main__":
    unittest.main()
