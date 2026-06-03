"""Experiment matrix expansion for task, prompt, model, repetition cells."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from .taxonomy import PROMPT_LEVELS, TaskSpec, load_taxonomy, project_root


@dataclass(frozen=True)
class ModelSpec:
    display_name: str
    model_id: str
    opencode_model_arg: str
    enabled: bool = True
    notes: str = ""

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "ModelSpec":
        return cls(
            display_name=str(row["display_name"]),
            model_id=str(row["model_id"]),
            opencode_model_arg=str(row["opencode_model_arg"]),
            enabled=bool(row.get("enabled", True)),
            notes=str(row.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MatrixCell:
    task: TaskSpec
    prompt_level: str
    model: ModelSpec
    repetition: int

    @property
    def run_id(self) -> str:
        safe_model = self.model.model_id.replace("/", "__").replace(":", "_")
        return f"{self.task.task_id}__{self.prompt_level}__{safe_model}__r{self.repetition}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_id": self.task.task_id,
            "prompt_level": self.prompt_level,
            "model_display_name": self.model.display_name,
            "model_id": self.model.model_id,
            "opencode_model_arg": self.model.opencode_model_arg,
            "repetition": self.repetition,
        }


def load_model_config(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def enabled_generation_models(path: str | Path) -> list[ModelSpec]:
    payload = load_model_config(path)
    return [
        ModelSpec.from_dict(dict(row))
        for row in payload.get("generation_models", [])
        if bool(row.get("enabled", True))
    ]


def judge_model(path: str | Path) -> ModelSpec:
    payload = load_model_config(path)
    return ModelSpec.from_dict(dict(payload["judge_model"]))


def optional_models(path: str | Path) -> list[ModelSpec]:
    payload = load_model_config(path)
    return [ModelSpec.from_dict(dict(row)) for row in payload.get("optional_models", [])]


def load_matrix_config(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def expand_matrix(
    *,
    matrix_path: str | Path,
    models_path: str | Path,
    taxonomy_path: str | Path | None = None,
) -> list[MatrixCell]:
    """Expand matrix config into concrete run cells."""

    matrix = load_matrix_config(matrix_path)
    taxonomy_file = Path(taxonomy_path) if taxonomy_path else project_root() / "benchmark" / "taxonomy" / "tasks.yaml"
    tasks = load_taxonomy(taxonomy_file)
    models = enabled_generation_models(models_path)

    include_task_ids = set(matrix.get("include_task_ids") or [])
    exclude_task_ids = set(matrix.get("exclude_task_ids") or [])
    include_prompt_levels = list(matrix.get("include_prompt_levels") or PROMPT_LEVELS)
    include_models = set(matrix.get("include_models") or [])
    repetitions = int(matrix.get("repetitions_per_cell", 1))

    if include_task_ids:
        tasks = [task for task in tasks if task.task_id in include_task_ids]
    if exclude_task_ids:
        tasks = [task for task in tasks if task.task_id not in exclude_task_ids]
    if include_models:
        models = [
            model
            for model in models
            if model.model_id in include_models
            or model.display_name in include_models
            or model.opencode_model_arg in include_models
        ]
    for level in include_prompt_levels:
        if level not in PROMPT_LEVELS:
            raise ValueError(f"unknown prompt level {level!r}; expected one of {PROMPT_LEVELS}")
    if repetitions < 1:
        raise ValueError("repetitions_per_cell must be >= 1")

    cells: list[MatrixCell] = []
    for task in tasks:
        for level in include_prompt_levels:
            for model in models:
                for repetition in range(1, repetitions + 1):
                    cells.append(MatrixCell(task=task, prompt_level=level, model=model, repetition=repetition))
    return cells
