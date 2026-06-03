import json
from pathlib import Path

from agentTaxonomy.report import summarize_runs


def test_summary_generation_writes_expected_files(tmp_path: Path) -> None:
    run = tmp_path / "run1"
    run.mkdir()
    (run / "metadata.json").write_text(json.dumps({"run_id": "run1", "prompt_level": "high_specificity", "exit_code": 0, "runtime_seconds": 1.2}), encoding="utf-8")
    (run / "model.json").write_text(json.dumps({"display_name": "Model", "model_id": "provider/model", "opencode_model_arg": "openrouter/provider/model"}), encoding="utf-8")
    (run / "task.json").write_text(json.dumps({"task_id": "task", "title": "Task", "consequence_class": "B", "task_mode": "repo_task"}), encoding="utf-8")
    (run / "judge_output.json").write_text(json.dumps({"failure_modes": []}), encoding="utf-8")
    (run / "score.json").write_text(json.dumps({"correctness_pass": True, "scope_pass": True, "deterministic_security_pass": True, "judge_security_pass": True, "binary_pass": True, "security_adjusted_success": True}), encoding="utf-8")

    result = summarize_runs(tmp_path)
    assert Path(result["summary_csv"]).exists()
    assert Path(result["summary_json"]).exists()
    assert Path(result["report_md"]).exists()
    assert result["run_count"] == 1
