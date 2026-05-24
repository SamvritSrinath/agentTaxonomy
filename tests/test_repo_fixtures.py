from pathlib import Path
import tempfile
import unittest

from agentTaxonomy.repo_fixtures import resolve_repo_fixture


class RepoFixtureTests(unittest.TestCase):
    def test_resolves_old_flat_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("", encoding="utf-8")
            (root / "oracle_checks.py").write_text("", encoding="utf-8")

            fixture = resolve_repo_fixture(root)

            self.assertEqual(fixture.fixture_root, root.resolve())
            self.assertEqual(fixture.source_repo, root.resolve())
            self.assertEqual(fixture.oracle_dir, root.resolve())
            self.assertEqual(fixture.legacy_inline_oracle, root.resolve() / "oracle_checks.py")

    def test_resolves_new_repo_oracle_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "repo").mkdir()
            (root / "oracle").mkdir()
            (root / "setup").mkdir()

            fixture = resolve_repo_fixture(root)

            self.assertEqual(fixture.source_repo, (root / "repo").resolve())
            self.assertEqual(fixture.oracle_dir, (root / "oracle").resolve())
            self.assertEqual(fixture.setup_dir, (root / "setup").resolve())


if __name__ == "__main__":
    unittest.main()
