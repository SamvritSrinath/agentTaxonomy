import tempfile
import unittest
from pathlib import Path

import yaml

from agentTaxonomy.db.session import reset_database
from agentTaxonomy.experiments import create_experiment_from_yaml, run_experiment_from_yaml, summarize_experiment


class ExperimentTests(unittest.TestCase):
    def test_fake_agent_experiment_runs_and_exports_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database_url = f"sqlite:///{root / 'workbench.sqlite'}"
            reset_database(database_url)
            design = root / "pilot.yaml"
            design.write_text(
                yaml.safe_dump(
                    {
                        "name": "pilot_fake_agent_test",
                        "agents": [{"name": "fake_safe", "command": "python scripts/fake_agent.py --mode safe"}],
                        "instances": ["flask_mvc_refactor__repo_edit__beginner"],
                        "evaluations": [
                            {"evidence_condition": "code_only"},
                            {"evidence_condition": "code_plus_trace"},
                        ],
                        "sandbox_profile": "repo_task_default",
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            created = create_experiment_from_yaml(design, database_url=database_url)
            result = run_experiment_from_yaml(design, output_root=root / "runs", database_url=database_url)
            output = summarize_experiment(root / "analysis.csv", database_url=database_url)
            analysis = Path(output).read_text(encoding="utf-8")

            self.assertEqual(created["name"], "pilot_fake_agent_test")
            self.assertEqual(len(result["runs"]), 1)
            self.assertIn("evidence_condition", analysis)
            self.assertIn("human_security_verdict", analysis)


if __name__ == "__main__":
    unittest.main()
