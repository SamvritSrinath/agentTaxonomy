from pathlib import Path
import tempfile
import textwrap
import unittest

from agentTaxonomy.repo_fixtures import resolve_repo_fixture
from agentTaxonomy.repo_oracles import run_repo_oracles
from agentTaxonomy.schema import (
    BenchmarkInstance,
    ConsequenceClass,
    HardSafetyOracleSpec,
    PermissionScope,
    RuntimeProfileSpec,
    SafeOutcome,
    SkillLevel,
    SoftReviewRubric,
    TaskMode,
    UtilityOracleSpec,
)


class RepoOracleTests(unittest.TestCase):
    def test_oracle_runs_from_fixture_against_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            fixture_root = root / "fixture"
            worktree = root / "run" / "worktree"
            (fixture_root / "repo").mkdir(parents=True)
            (fixture_root / "oracle").mkdir()
            worktree.mkdir(parents=True)
            (worktree / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            (fixture_root / "oracle" / "oracle_checks.py").write_text(
                textwrap.dedent(
                    """
                    from __future__ import annotations
                    import argparse, json
                    from pathlib import Path
                    parser = argparse.ArgumentParser()
                    parser.add_argument("--repo")
                    parser.add_argument("--output")
                    args = parser.parse_args()
                    passed = (Path(args.repo) / "app.py").read_text() == "VALUE = 1\\n"
                    Path(args.output).write_text(json.dumps({"passed": passed, "checks": [{"id": "value", "passed": passed}]}))
                    raise SystemExit(0 if passed else 1)
                    """
                ),
                encoding="utf-8",
            )

            report = run_repo_oracles(
                instance=self._instance(),
                fixture=resolve_repo_fixture(fixture_root),
                worktree=worktree,
                output_dir=root / "run",
                timeout_seconds=30,
            )

            self.assertTrue(report["executed"])
            self.assertTrue(report["passed"])
            self.assertEqual(report["cwd"], str((fixture_root / "oracle").resolve()))

    def _instance(self) -> BenchmarkInstance:
        return BenchmarkInstance(
            instance_id="repo_oracle__repo_edit__beginner",
            task_mode=TaskMode.REPO_TASK,
            problem_class="Repo task",
            subject_area="Repo maintenance",
            agent_prompt="Edit app.",
            agent_prompt_path="prompt.md",
            skill_level=SkillLevel.BEGINNER,
            permission_scope=PermissionScope.FILESYSTEM_WRITE,
            consequence_class=ConsequenceClass.STATEFUL_LOCALLY_REVERSIBLE,
            expected_safe_outcome=SafeOutcome.SAFE_COMPLETE,
            utility_oracles=UtilityOracleSpec(command="", fail_to_pass=[], pass_to_pass=[]),
            hard_safety_oracles=HardSafetyOracleSpec([], [], [], [], [], [], [], []),
            soft_review_rubric=SoftReviewRubric(rubric_id="repo_oracle", questions=[]),
            split="dev",
            visibility="public",
            gold_strategy="",
            repo="repo",
            base_commit="0" * 40,
            runtime_profiles=[RuntimeProfileSpec(name="static", default=True)],
        )


if __name__ == "__main__":
    unittest.main()
