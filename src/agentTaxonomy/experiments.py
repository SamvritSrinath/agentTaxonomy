"""YAML experiment runner for local repo-task pilot matrices."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .db import ingest_evaluation, ingest_run, init_database
from .db.exports import export_wide
from .db.ingest import sha256_file
from .db.services import create_experiment
from .db.session import project_root, session_scope
from .harness import BenchmarkHarness
from .repo_runner import run_repo_task


def load_experiment_yaml(path: Path) -> dict[str, Any]:
    """Load and validate the v1 experiment YAML schema."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("experiment YAML must contain a mapping")
    for key in ["name", "agents", "instances", "evaluations", "sandbox_profile"]:
        if key not in payload:
            raise ValueError(f"experiment YAML missing {key!r}")
    return payload


def create_experiment_from_yaml(path: Path, *, database_url: str | None = None) -> dict[str, Any]:
    """Store a YAML experiment design in the workbench database."""
    init_database(database_url)
    payload = load_experiment_yaml(path)
    with session_scope(database_url) as session:
        return create_experiment(
            session,
            {
                "name": payload["name"],
                "description": payload.get("description"),
                "design": payload,
                "source_file": str(path.resolve()),
                "source_file_hash": sha256_file(path.resolve()),
            },
        )


def run_experiment_from_yaml(
    path: Path,
    *,
    output_root: Path,
    database_url: str | None = None,
) -> dict[str, Any]:
    """Execute every agent/instance pair in a v1 YAML experiment."""
    design = load_experiment_yaml(path)
    create_experiment_from_yaml(path, database_url=database_url)
    harness = BenchmarkHarness(project_root())
    experiment_root = output_root / str(design["name"])
    run_results: list[dict[str, Any]] = []
    for agent in design["agents"]:
        agent_name = str(agent["name"])
        command = _normalize_agent_command(str(agent["command"]))
        for instance_id in design["instances"]:
            instance = harness.instance_by_id(str(instance_id))
            if not instance.repo:
                raise ValueError(f"{instance.instance_id} is missing repo fixture path")
            output_dir = experiment_root / instance.instance_id / agent_name
            result = run_repo_task(
                instance=instance,
                repo=(project_root() / instance.repo).resolve(),
                agent_cmd=command,
                profile_name="static",
                output_dir=output_dir,
                sandbox_profile_name=str(design["sandbox_profile"]),
            )
            ingest_result = ingest_run(Path(result.output_dir), database_url=database_url)
            evaluations = []
            for evaluation in design["evaluations"]:
                evaluations.append(
                    ingest_evaluation(
                        Path(result.output_dir),
                        evidence_condition=str(evaluation["evidence_condition"]),
                        database_url=database_url,
                    ).__dict__
                )
            run_results.append(
                {
                    "instance_id": instance.instance_id,
                    "agent_name": agent_name,
                    "run_dir": result.output_dir,
                    "ingest": ingest_result.__dict__,
                    "evaluations": evaluations,
                }
            )
    return {"name": design["name"], "runs": run_results}


def summarize_experiment(output: Path, *, database_url: str | None = None) -> str:
    """Export the wide analysis table for experiment review."""
    return str(export_wide(output, database_url=database_url))


def write_example_experiment(path: Path) -> Path:
    """Write the canonical pilot fake-agent experiment YAML."""
    payload = {
        "name": "pilot_fake_agent_v1",
        "agents": [
            {"name": "fake_safe", "command": "python scripts/fake_agent.py --mode safe"},
            {"name": "fake_buggy", "command": "python scripts/fake_agent.py --mode buggy"},
        ],
        "instances": [
            "flask_mvc_refactor__repo_edit__beginner",
            "flask_mvc_refactor__repo_edit__intermediate",
            "flask_mvc_refactor__repo_edit__expert",
            "api_rate_limiting__repo_edit__beginner",
            "api_rate_limiting__repo_edit__intermediate",
            "api_rate_limiting__repo_edit__expert",
        ],
        "evaluations": [{"evidence_condition": "code_only"}, {"evidence_condition": "code_plus_trace"}],
        "sandbox_profile": "repo_task_default",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _normalize_agent_command(command: str) -> str:
    """Resolve the fake-agent script path while preserving the YAML command shape."""
    fake_agent = project_root() / "scripts" / "fake_agent.py"
    if "scripts/fake_agent.py" in command and fake_agent.exists():
        return command.replace("scripts/fake_agent.py", str(fake_agent))
    return command
