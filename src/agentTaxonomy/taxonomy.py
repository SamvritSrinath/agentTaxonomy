"""YAML-backed task taxonomy for the OpenCode/OpenRouter matrix runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROMPT_LEVELS = ("low_specificity", "medium_specificity", "high_specificity")


def project_root() -> Path:
    """Return the repository root."""

    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class TaskSpec:
    """One task family in ``benchmark/taxonomy/tasks.yaml``."""

    task_id: str
    title: str
    consequence_class: str
    task_mode: str
    permission_profile: str
    fixture_path: str
    allowed_paths: list[str] = field(default_factory=list)
    forbidden_paths: list[str] = field(default_factory=list)
    expected_artifacts: list[str] = field(default_factory=list)
    deterministic_checks: list[str] = field(default_factory=list)
    judge_rubric_hooks: list[str] = field(default_factory=list)
    destructive_actions_require_confirmation: bool = False
    network_policy: str = "disabled"
    git_policy: dict[str, Any] = field(default_factory=dict)
    externalization_policy: str = "localhost_only"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "TaskSpec":
        required = [
            "task_id",
            "title",
            "consequence_class",
            "task_mode",
            "permission_profile",
            "fixture_path",
        ]
        missing = [key for key in required if key not in row]
        if missing:
            raise ValueError(f"task row missing required fields {missing}: {row!r}")
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        payload = {key: value for key, value in row.items() if key in known}
        payload["allowed_paths"] = list(payload.get("allowed_paths") or [])
        payload["forbidden_paths"] = list(payload.get("forbidden_paths") or [])
        payload["expected_artifacts"] = list(payload.get("expected_artifacts") or [])
        payload["deterministic_checks"] = list(payload.get("deterministic_checks") or [])
        payload["judge_rubric_hooks"] = list(payload.get("judge_rubric_hooks") or [])
        payload["git_policy"] = dict(payload.get("git_policy") or {})
        payload["tags"] = list(payload.get("tags") or [])
        payload["metadata"] = dict(payload.get("metadata") or {})
        return cls(**payload)

    def fixture_root(self, root: Path | None = None) -> Path:
        base = root or project_root()
        path = Path(self.fixture_path)
        return path if path.is_absolute() else base / path

    def prompt_path(self, level: str, root: Path | None = None) -> Path:
        if level not in PROMPT_LEVELS:
            raise ValueError(f"unknown prompt level {level!r}; expected one of {PROMPT_LEVELS}")
        base = root or project_root()
        return base / "benchmark" / "prompts" / self.task_id / f"{level}.md"

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "consequence_class": self.consequence_class,
            "task_mode": self.task_mode,
            "permission_profile": self.permission_profile,
            "fixture_path": self.fixture_path,
            "allowed_paths": self.allowed_paths,
            "forbidden_paths": self.forbidden_paths,
            "expected_artifacts": self.expected_artifacts,
            "deterministic_checks": self.deterministic_checks,
            "judge_rubric_hooks": self.judge_rubric_hooks,
            "destructive_actions_require_confirmation": self.destructive_actions_require_confirmation,
            "network_policy": self.network_policy,
            "git_policy": self.git_policy,
            "externalization_policy": self.externalization_policy,
            "tags": self.tags,
            "metadata": self.metadata,
        }


def load_taxonomy(path: str | Path | None = None) -> list[TaskSpec]:
    """Load task families from ``tasks.yaml``."""

    taxonomy_path = Path(path) if path else project_root() / "benchmark" / "taxonomy" / "tasks.yaml"
    payload = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8")) or {}
    rows = payload.get("tasks", [])
    if not isinstance(rows, list):
        raise ValueError(f"{taxonomy_path} must contain a top-level tasks list")
    tasks = [TaskSpec.from_dict(dict(row)) for row in rows]
    seen: set[str] = set()
    duplicates: list[str] = []
    for task in tasks:
        if task.task_id in seen:
            duplicates.append(task.task_id)
        seen.add(task.task_id)
    if duplicates:
        raise ValueError(f"duplicate task_id values in {taxonomy_path}: {sorted(duplicates)}")
    return tasks


def task_by_id(task_id: str, path: str | Path | None = None) -> TaskSpec:
    """Return one task by id."""

    for task in load_taxonomy(path):
        if task.task_id == task_id:
            return task
    raise KeyError(f"unknown task id: {task_id}")


def read_prompt(task: TaskSpec, level: str, root: Path | None = None) -> str:
    """Read an agent-facing prompt for a task/prompt-level cell."""

    prompt_path = task.prompt_path(level, root)
    if not prompt_path.exists():
        raise FileNotFoundError(f"prompt file does not exist: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8").strip() + "\n"


def validate_taxonomy_files(root: Path | None = None) -> dict[str, Any]:
    """Check prompts and fixture paths for all task families."""

    base = root or project_root()
    missing_prompts: list[str] = []
    missing_fixtures: list[str] = []
    tasks = load_taxonomy(base / "benchmark" / "taxonomy" / "tasks.yaml")
    for task in tasks:
        fixture = task.fixture_root(base)
        if not fixture.exists():
            missing_fixtures.append(str(fixture))
        for level in PROMPT_LEVELS:
            prompt = task.prompt_path(level, base)
            if not prompt.exists():
                missing_prompts.append(str(prompt))
    return {
        "task_count": len(tasks),
        "prompt_count": len(tasks) * len(PROMPT_LEVELS) - len(missing_prompts),
        "missing_prompts": missing_prompts,
        "missing_fixtures": missing_fixtures,
        "valid": not missing_prompts and not missing_fixtures,
    }
