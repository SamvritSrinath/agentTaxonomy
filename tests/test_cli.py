from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
