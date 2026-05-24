from pathlib import Path
import tempfile
import unittest

from agentTaxonomy.repo_supply_chain import enrich_repo_supply_chain


class RepoSupplyChainTests(unittest.TestCase):
    def test_repo_supply_chain_reports_added_unpinned_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            worktree = root / "worktree"
            worktree.mkdir()
            (worktree / "requirements.txt").write_text("flask-limiter\n", encoding="utf-8")
            diff_path = root / "diff.patch"
            diff_path.write_text("+++ b/requirements.txt\n+flask-limiter\n", encoding="utf-8")

            report = enrich_repo_supply_chain(worktree=worktree, diff_path=diff_path)

            summary = report["repo_supply_chain"]
            self.assertEqual(summary["package_manager_files_changed"], ["requirements.txt"])
            self.assertEqual(summary["new_dependencies"], ["flask-limiter"])
            self.assertEqual(summary["unpinned_dependencies"], ["flask-limiter"])
            self.assertEqual(summary["supply_chain_risk"], "medium")


if __name__ == "__main__":
    unittest.main()
