import json
from pathlib import Path

from agentTaxonomy.matrix import enabled_generation_models, judge_model
from agentTaxonomy.model_validation import validate_models


def test_model_config_loads() -> None:
    models = enabled_generation_models("benchmark/configs/models.yaml")
    assert len(models) == 12
    assert judge_model("benchmark/configs/models.yaml").model_id == "anthropic/claude-opus-4.7"
    assert all(not model.model_id.endswith(":free") for model in models)


def test_openrouter_validation_report_writes(monkeypatch, tmp_path: Path) -> None:
    models = enabled_generation_models("benchmark/configs/models.yaml")
    ids = [model.model_id for model in models] + [judge_model("benchmark/configs/models.yaml").model_id]

    monkeypatch.setattr("agentTaxonomy.model_validation.list_openrouter_model_ids", lambda api_key=None: ids)
    monkeypatch.setattr("agentTaxonomy.model_validation.probe_opencode_models", lambda configured_args: {"available": False, "configured_args_checked": configured_args})
    output = tmp_path / "model_validation_report.json"
    report = validate_models("benchmark/configs/models.yaml", output_path=output)

    assert report["valid"]
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8"))["valid"]
