from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class TaskMode(StrEnum):
    REPO_TASK = "repo_task"
    GENERATIVE_TASK = "generative_task"


class SkillLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


class PermissionScope(StrEnum):
    READ_ONLY = "read_only"
    FILESYSTEM_WRITE = "filesystem_write"
    SHELL_EXECUTION = "shell_execution"
    DATABASE_ACCESS = "database_access"
    NETWORK_ACCESS = "network_access"
    EXTERNAL_API_ACCESS = "external_api_access"


class ConsequenceClass(StrEnum):
    READ_ONLY_REVERSIBLE = "A_read_only_reversible"
    STATEFUL_LOCALLY_REVERSIBLE = "B_stateful_locally_reversible"
    EXTERNALLY_CONSEQUENTIAL = "C_externally_consequential"
    CATASTROPHIC_IRREVERSIBLE = "D_catastrophic_irreversible"


class SafeOutcome(StrEnum):
    SAFE_COMPLETE = "safe_complete"
    HALT = "halt"
    REFUSE = "refuse"
    ISOLATE_THEN_COMPLETE = "isolate_then_complete"


class EventType(StrEnum):
    AGENT_PROMPT_RENDERED = "agent_prompt_rendered"
    AGENT_OUTPUT_RECEIVED = "agent_output_received"
    PROMPT_CONTEXT_LOAD = "prompt_context_load"
    COMMAND_PROPOSED = "command_proposed"
    COMMAND_EXECUTED = "command_executed"
    FILE_EDIT = "file_edit"
    GIT_ACTION = "git_action"
    TEST_RUN = "test_run"
    DB_ACTION = "db_action"
    NETWORK_ACTION = "network_action"
    SECRET_ACCESS = "secret_access"
    FINAL_PATCH = "final_patch"
    FINAL_RESPONSE = "final_response"
    AGENT_DECISION = "agent_decision"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CATASTROPHIC = "catastrophic"


@dataclass(frozen=True)
class UtilityOracleSpec:
    command: str
    fail_to_pass: list[str]
    pass_to_pass: list[str]


@dataclass(frozen=True)
class HardSafetyOracleSpec:
    destructive_command_patterns: list[str]
    destructive_sql_patterns: list[str]
    forbidden_write_prefixes: list[str]
    canary_hosts: list[str]
    secret_identifiers: list[str]
    forbidden_git_patterns: list[str]
    backdoor_indicators: list[str]
    test_disable_indicators: list[str]


@dataclass(frozen=True)
class RubricQuestion:
    rubric_id: str
    question: str
    pass_condition: str


@dataclass(frozen=True)
class SoftReviewRubric:
    rubric_id: str
    questions: list[RubricQuestion]


@dataclass(frozen=True)
class BenchmarkInstance:
    instance_id: str
    task_mode: TaskMode
    problem_class: str
    subject_area: str
    agent_prompt: str
    agent_prompt_path: str
    skill_level: SkillLevel
    permission_scope: PermissionScope
    consequence_class: ConsequenceClass
    expected_safe_outcome: SafeOutcome
    utility_oracles: UtilityOracleSpec
    hard_safety_oracles: HardSafetyOracleSpec
    soft_review_rubric: SoftReviewRubric
    split: str
    visibility: str
    gold_strategy: str
    repo: str | None = None
    base_commit: str | None = None
    tags: list[str] = field(default_factory=list)
    runtime_profiles: list[str] = field(default_factory=list)
    expected_artifacts: list[str] = field(default_factory=list)
    allowed_output_files: list[str] = field(default_factory=list)
    language: str | None = None
    frameworks: list[str] = field(default_factory=list)
    domain_failure_modes: list[str] = field(default_factory=list)

    def validate(self, project_root: Path) -> None:
        if self.split not in {"dev", "test"}:
            raise ValueError(f"{self.instance_id} has unsupported split {self.split!r}")
        if self.visibility not in {"public", "hidden"}:
            raise ValueError(f"{self.instance_id} has unsupported visibility {self.visibility!r}")
        required_common_strings = {
            "problem_class": self.problem_class,
            "subject_area": self.subject_area,
            "agent_prompt": self.agent_prompt,
            "agent_prompt_path": self.agent_prompt_path,
        }
        missing_common = [name for name, value in required_common_strings.items() if not value.strip()]
        if missing_common:
            raise ValueError(f"{self.instance_id} missing common fields: {', '.join(missing_common)}")

        if self.task_mode == TaskMode.REPO_TASK:
            required_repo_fields = {
                "repo": self.repo,
                "base_commit": self.base_commit,
            }
            missing = [name for name, value in required_repo_fields.items() if value is None]
            if missing:
                raise ValueError(f"{self.instance_id} missing repo_task fields: {', '.join(missing)}")
            assert self.base_commit is not None
            if len(self.base_commit) != 40 or any(ch not in "0123456789abcdef" for ch in self.base_commit):
                raise ValueError(f"{self.instance_id} has an invalid base commit: {self.base_commit}")
            return

        if self.task_mode == TaskMode.GENERATIVE_TASK:
            required_generative_fields = {
                "expected_artifacts": self.expected_artifacts,
                "allowed_output_files": self.allowed_output_files,
                "language": self.language,
                "frameworks": self.frameworks,
                "domain_failure_modes": self.domain_failure_modes,
            }
            missing = [name for name, value in required_generative_fields.items() if not value]
            if missing:
                raise ValueError(f"{self.instance_id} missing generative_task fields: {', '.join(missing)}")
            return

        raise ValueError(f"{self.instance_id} has unsupported task_mode {self.task_mode!r}")


@dataclass(frozen=True)
class BenchmarkCatalog:
    benchmark_name: str
    version: str
    summary: str
    instances: list[BenchmarkInstance]

    def validate(self, project_root: Path) -> None:
        seen: set[str] = set()
        for instance in self.instances:
            if instance.instance_id in seen:
                raise ValueError(f"duplicate instance_id {instance.instance_id}")
            seen.add(instance.instance_id)
            instance.validate(project_root)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TraceEvent:
    event_id: str
    event_type: EventType
    timestamp: str
    payload: dict[str, Any]
    actor: str = "agent"


@dataclass(frozen=True)
class OracleFinding:
    oracle_id: str
    passed: bool
    severity: Severity
    message: str
    event_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class UtilityScore:
    score: float
    solved: bool
    fail_to_pass_resolved: int
    fail_to_pass_total: int
    pass_to_pass_maintained: int
    pass_to_pass_total: int


@dataclass(frozen=True)
class HardSafetyScore:
    score: float
    catastrophic: bool
    unsafe_proposal_rate: float
    clarification_rate: float
    recovery_score: float
    findings: list[OracleFinding]


@dataclass(frozen=True)
class SoftReviewItem:
    rubric_id: str
    passed: bool
    confidence: float
    rationale: str
    severity: str = "info"
    finding: str = ""
    evidence: str = ""
    action: str = ""
    failure_modes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SoftSafetyScore:
    score: float
    needs_human_review: bool
    items: list[SoftReviewItem]
    binary_pass: bool = True
    critical_findings: list[str] = field(default_factory=list)
    downstream_risks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RunScore:
    instance_id: str
    task_mode: str
    problem_class: str
    subject_area: str
    skill_level: str
    permission_scope: str
    consequence_class: str
    expected_safe_outcome: str
    observed_outcome: str
    utility_score: UtilityScore
    hard_safety_score: HardSafetyScore
    soft_safety_score: SoftSafetyScore
    security_adjusted_success: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
