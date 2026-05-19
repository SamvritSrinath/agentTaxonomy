# Task Authoring

Add new benchmark tasks under `benchmark/task_catalog/subject_areas/<task_id>/`. Each task expands
into three instances: `<task_id>__beginner`, `<task_id>__intermediate`, and `<task_id>__expert`.

## Directory layout

```text
benchmark/task_catalog/subject_areas/<task_id>/
├── task.json
└── levels/
    ├── beginner.md
    ├── intermediate.md
    └── expert.md
```

## Prompt guidelines

- Write `.md` files as **agent-facing prompts**, not benchmark metadata.
- Do not reference skill labels, rubrics, permission scopes, or benchmark internals in prompt text.
- Encode difficulty through task complexity, constraints, artifacts, and engineering requirements.
- Keep prompts self-contained; evaluation metadata is supplied to the judge separately.

## `task.json` template

```json
{
  "task_id": "example_task",
  "problem_class": "Readable task family label",
  "subject_area": "Domain label",
  "levels": {
    "beginner": "levels/beginner.md",
    "intermediate": "levels/intermediate.md",
    "expert": "levels/expert.md"
  },
  "permission_scope": "shell_execution",
  "consequence_class": "B_stateful_locally_reversible",
  "expected_safe_outcome": "safe_complete",
  "expected_artifacts": ["source_code", "tests", "documentation"],
  "allowed_output_files": ["src/**", "README.md"],
  "language": "python",
  "frameworks": [],
  "domain_failure_modes": ["example_failure_mode"],
  "gold_strategy": "Brief description of a safe, complete solution approach.",
  "tags": ["example"],
  "rubric_questions": [
    {
      "rubric_id": "task_specific_control",
      "question": "Does the solution satisfy a task-specific safety requirement?",
      "pass_condition": "Concrete evidence in the trace or output that the requirement is met."
    }
  ]
}
```

After editing, run `build-catalog` and `validate-catalog`. See [Getting Started](getting-started.md).
