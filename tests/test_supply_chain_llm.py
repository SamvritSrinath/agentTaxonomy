import json
import unittest
from unittest.mock import patch

from agentTaxonomy.supply_chain_advisory import lookup_osv_advisories
from agentTaxonomy.supply_chain_llm import parse_dependency_extraction


class SupplyChainLlmTests(unittest.TestCase):
    def test_parse_dependency_extraction_accepts_fenced_json(self) -> None:
        payload = {
            "dependencies": [
                {
                    "ecosystem": "Maven",
                    "name": "org.apache.spark:spark-sql_2.12",
                    "version": "3.5.1",
                    "source": "build.sbt",
                    "pinned": True,
                }
            ],
            "install_patterns": [],
            "risk_notes": ["unpinned docker base"],
        }
        content = "```json\n" + json.dumps(payload) + "\n```"
        parsed = parse_dependency_extraction(content)
        self.assertEqual(len(parsed["dependencies"]), 1)
        self.assertTrue(any(f["id"] == "unpinned_dependency" for f in parsed["findings"]))

    @patch("agentTaxonomy.supply_chain_advisory._query_batch")
    def test_osv_lookup_returns_advisory_findings(self, mock_batch) -> None:
        mock_batch.return_value = [
            {
                "vulns": [
                    {
                        "id": "GHSA-xxxx-yyyy-zzzz",
                        "summary": "Example vulnerability",
                    }
                ]
            }
        ]
        findings = lookup_osv_advisories(
            [{"ecosystem": "PyPI", "name": "jinja2", "version": "2.0.0", "source": "requirements.txt"}]
        )
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0]["id"].startswith("osv_"))
        self.assertFalse(findings[0]["blocking"])


if __name__ == "__main__":
    unittest.main()
