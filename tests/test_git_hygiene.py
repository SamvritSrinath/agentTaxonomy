from pathlib import Path


def test_gitignore_contains_run_artifact_paths() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    for pattern in [
        "runs/",
        "exports/",
        "reports/raw/",
        "benchmark/runs/",
        "benchmark/worktrees/",
        "benchmark/tmp/",
        "*.jsonl",
        "*_stdout.txt",
        "*_stderr.txt",
        "model_outputs/",
        "judge_outputs/",
        "opencode_sessions/",
        ".opencode/",
        "worktree_diffs/",
        "generated_artifacts/",
    ]:
        assert pattern in gitignore


def test_overnight_script_does_not_run_git_mutations() -> None:
    script = Path("scripts/run_overnight_opencode_matrix.sh").read_text(encoding="utf-8").lower()
    assert "git add" not in script
    assert "git commit" not in script
    assert "git push" not in script
