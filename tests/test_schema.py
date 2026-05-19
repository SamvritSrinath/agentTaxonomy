import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SchemaTests(unittest.TestCase):
    def test_instance_schema_declares_shared_task_modes(self) -> None:
        schema = json.loads((PROJECT_ROOT / "schemas" / "instance.schema.json").read_text(encoding="utf-8"))

        self.assertIn("task_mode", schema["required"])
        self.assertEqual(schema["properties"]["task_mode"]["enum"], ["repo_task", "generative_task"])
        self.assertEqual(schema["properties"]["skill_level"]["enum"], ["beginner", "intermediate", "expert"])
        self.assertEqual(
            schema["properties"]["consequence_class"]["enum"],
            [
                "A_read_only_reversible",
                "B_stateful_locally_reversible",
                "C_externally_consequential",
                "D_catastrophic_irreversible",
            ],
        )

    def test_instance_schema_has_mode_specific_requirements(self) -> None:
        schema = json.loads((PROJECT_ROOT / "schemas" / "instance.schema.json").read_text(encoding="utf-8"))
        branches = schema["allOf"]

        repo_branch = next(
            branch for branch in branches if branch["if"]["properties"]["task_mode"]["const"] == "repo_task"
        )
        generative_branch = next(
            branch for branch in branches if branch["if"]["properties"]["task_mode"]["const"] == "generative_task"
        )

        self.assertIn("repo", repo_branch["then"]["required"])
        self.assertIn("base_commit", repo_branch["then"]["required"])
        self.assertNotIn("prompt_variant", schema["properties"])
        self.assertNotIn("attack_surface", schema["properties"])
        self.assertNotIn("overlay_bundle", schema["properties"])
        self.assertIn("expected_artifacts", generative_branch["then"]["required"])
        self.assertIn("allowed_output_files", generative_branch["then"]["required"])
        self.assertIn("domain_failure_modes", generative_branch["then"]["required"])

    def test_run_score_schema_requires_actionable_soft_review_fields(self) -> None:
        schema = json.loads((PROJECT_ROOT / "schemas" / "run_score.schema.json").read_text(encoding="utf-8"))
        soft_schema = schema["properties"]["soft_safety_score"]
        item_schema = soft_schema["properties"]["items"]["items"]

        self.assertIn("binary_pass", soft_schema["required"])
        self.assertIn("critical_findings", soft_schema["required"])
        self.assertIn("downstream_risks", soft_schema["required"])
        self.assertIn("severity", item_schema["required"])
        self.assertIn("evidence", item_schema["required"])
        self.assertIn("action", item_schema["required"])
        self.assertIn("failure_modes", item_schema["required"])


if __name__ == "__main__":
    unittest.main()
