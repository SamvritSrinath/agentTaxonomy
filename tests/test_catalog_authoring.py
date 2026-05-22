import tempfile
import unittest
from pathlib import Path

from agentTaxonomy.catalog_authoring import create_catalog_task, update_canonical_prompt, validate_task_id


class CatalogAuthoringTests(unittest.TestCase):
    def test_validate_task_id(self) -> None:
        self.assertEqual(validate_task_id("My-Task"), "my_task")

    def test_create_and_update_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "benchmark" / "generated").mkdir(parents=True)
            result = create_catalog_task(
                task_id="ui_test_task",
                subject_area="Test domain",
                problem_class="Test problem",
                beginner_prompt="Beginner task prompt.",
                intermediate_prompt="Intermediate task prompt.",
                expert_prompt="Expert task prompt.",
                root=root,
                rebuild_catalog=True,
                ingest_catalog_db=False,
            )
            self.assertEqual(result["task_id"], "ui_test_task")
            task_dir = root / "benchmark" / "task_catalog" / "subject_areas" / "ui_test_task"
            self.assertTrue((task_dir / "task.json").exists())
            self.assertEqual((task_dir / "levels" / "beginner.md").read_text(encoding="utf-8").strip(), "Beginner task prompt.")

            update = update_canonical_prompt(
                "ui_test_task__expert",
                "Updated expert prompt.",
                root=root,
                rebuild_catalog=True,
                ingest_catalog_db=False,
            )
            self.assertIn("expert.md", update["prompt_path"])
            self.assertEqual(
                (task_dir / "levels" / "expert.md").read_text(encoding="utf-8").strip(),
                "Updated expert prompt.",
            )


if __name__ == "__main__":
    unittest.main()
