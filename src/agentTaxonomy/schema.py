"""Core dataclasses and enums for benchmark instances, traces, and scores."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class TaskMode(StrEnum):
    """How a benchmark instance is executed and evaluated.

    Values:
        REPO_TASK: Agent works in a checked-out repository at a fixed commit.
        GENERATIVE_TASK: Agent produces artifacts from a standalone prompt.
    """

    REPO_TASK = "repo_task"
    GENERATIVE_TASK = "generative_task"


class SkillLevel(StrEnum):
    """Declared difficulty tier for a benchmark instance.

    Values:
        BEGINNER: Reduced scope and constraints.
        INTERMEDIATE: Moderate engineering requirements.
        EXPERT: Production-oriented requirements and edge cases.
    """

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


class PermissionScope(StrEnum):
    """Maximum capabilities the agent is allowed to exercise for an instance."""

    READ_ONLY = "read_only"
    FILESYSTEM_WRITE = "filesystem_write"
    SHELL_EXECUTION = "shell_execution"
    DATABASE_ACCESS = "database_access"
    NETWORK_ACCESS = "network_access"
    EXTERNAL_API_ACCESS = "external_api_access"


class ConsequenceClass(StrEnum):
    """Severity of harm if the agent acts unsafely or incorrectly."""

    READ_ONLY_REVERSIBLE = "A_read_only_reversible"
    STATEFUL_LOCALLY_REVERSIBLE = "B_stateful_locally_reversible"
    EXTERNALLY_CONSEQUENTIAL = "C_externally_consequential"
    CATASTROPHIC_IRREVERSIBLE = "D_catastrophic_irreversible"


class SafeOutcome(StrEnum):
    """Expected safe behavior for a successfully handled instance."""

    SAFE_COMPLETE = "safe_complete"
    HALT = "halt"
    REFUSE = "refuse"
    ISOLATE_THEN_COMPLETE = "isolate_then_complete"


class EventType(StrEnum):
    """Semantic categories for entries in a run trace JSONL file."""

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
    """Severity assigned to a hard-safety oracle finding."""

    INFO = "info"
    WARNING = "warning"
    CATASTROPHIC = "catastrophic"


@dataclass(frozen=True)
class UtilityOracleSpec:
    """Test harness specification for utility scoring.

    Attributes:
        command: Command used to run tests (may be empty for generative tasks).
        fail_to_pass: Test names that must flip from fail to pass.
        pass_to_pass: Regression tests that must remain passing.
    """

    command: str
    fail_to_pass: list[str]
    pass_to_pass: list[str]


@dataclass(frozen=True)
class HardSafetyOracleSpec:
    """Pattern lists for deterministic hard-safety checks over traces.

    Attributes:
        destructive_command_patterns: Regex patterns for unsafe shell commands.
        destructive_sql_patterns: Regex patterns for destructive SQL.
        forbidden_write_prefixes: Path prefixes that must not be written.
        canary_hosts: Hostnames that must not be contacted.
        secret_identifiers: Secret names that must not be accessed.
        forbidden_git_patterns: Regex patterns for unsafe git operations.
        backdoor_indicators: Substrings indicating persistence or exfiltration.
        test_disable_indicators: Substrings indicating disabled or bypassed tests.
    """

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
    """Single binary soft-review criterion.

    Attributes:
        rubric_id: Stable identifier referenced in scores and overrides.
        question: Human-readable question posed to the judge.
        pass_condition: Concrete rule for assigning a pass verdict.
    """

    rubric_id: str
    question: str
    pass_condition: str


@dataclass(frozen=True)
class SoftReviewRubric:
    """Collection of soft-review questions for one benchmark instance.

    Attributes:
        rubric_id: Name of the rubric set (typically derived from task id).
        questions: Ordered rubric items graded by the soft judge.
    """

    rubric_id: str
    questions: list[RubricQuestion]


@dataclass(frozen=True)
class BenchmarkInstance:
    """One evaluable benchmark task (for example ``task_id__beginner``).

    Holds taxonomy labels, agent prompt text, oracle configuration, and generative
    metadata. Validate with :meth:`validate` before publishing to the catalog.
    """

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
        """Verify required fields and mode-specific constraints.

        Args:
            project_root: Repository root (reserved for future path checks).

        Raises:
            ValueError: If split, visibility, or mode-specific fields are invalid.

        Use when:
            Building or loading the catalog and before scoring production runs.
        """
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
    """Top-level container for all benchmark instances in a release.

    Attributes:
        benchmark_name: Short name of the benchmark suite.
        version: Catalog schema or content version string.
        summary: Human-readable description for documentation.
        instances: All :class:`BenchmarkInstance` records in this catalog.
    """

    benchmark_name: str
    version: str
    summary: str
    instances: list[BenchmarkInstance]

    def validate(self, project_root: Path) -> None:
        """Validate every instance and ensure instance ids are unique.

        Args:
            project_root: Passed to each instance's :meth:`BenchmarkInstance.validate`.

        Raises:
            ValueError: On duplicate ids or invalid instance fields.

        Use when:
            Running ``validate-catalog`` or before writing ``catalog.json``.
        """
        seen: set[str] = set()
        for instance in self.instances:
            if instance.instance_id in seen:
                raise ValueError(f"duplicate instance_id {instance.instance_id}")
            seen.add(instance.instance_id)
            instance.validate(project_root)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the catalog to a JSON-compatible dictionary.

        Returns:
            Nested dict suitable for ``json.dumps``.

        Use when:
            Writing ``benchmark/generated/catalog.json``.
        """
        return asdict(self)


@dataclass(frozen=True)
class TraceEvent:
    """One line in a run trace (``trace.jsonl``).

    Attributes:
        event_id: Unique identifier for the event.
        event_type: Semantic category from :class:`EventType`.
        timestamp: ISO-8601 UTC timestamp.
        payload: Event-specific structured data.
        actor: Entity that produced the event (for example ``"agent"`` or ``"harness"``).
    """

    event_id: str
    event_type: EventType
    timestamp: str
    payload: dict[str, Any]
    actor: str = "agent"


@dataclass(frozen=True)
class OracleFinding:
    """Result of a single hard-safety oracle check.

    Attributes:
        oracle_id: Identifier of the oracle that produced the finding.
        passed: Whether the check passed.
        severity: :class:`Severity` of the finding.
        message: Human-readable explanation.
        event_ids: Trace events that contributed to the finding.
    """

    oracle_id: str
    passed: bool
    severity: Severity
    message: str
    event_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class UtilityScore:
    """Utility (task completion) metrics for a run.

    Attributes:
        score: Normalized score in ``[0.0, 1.0]``.
        solved: Whether all required tests passed when oracles are defined.
        fail_to_pass_resolved: Count of fail-to-pass tests fixed.
        fail_to_pass_total: Total fail-to-pass tests expected.
        pass_to_pass_maintained: Count of regressions still passing.
        pass_to_pass_total: Total pass-to-pass tests expected.
    """

    score: float
    solved: bool
    fail_to_pass_resolved: int
    fail_to_pass_total: int
    pass_to_pass_maintained: int
    pass_to_pass_total: int


@dataclass(frozen=True)
class HardSafetyScore:
    """Deterministic safety metrics derived from trace oracles.

    Attributes:
        score: ``1.0`` if no catastrophic event; ``0.0`` otherwise.
        catastrophic: Whether any catastrophic oracle fired.
        unsafe_proposal_rate: Fraction of proposed commands matching unsafe patterns.
        clarification_rate: Fraction of trace events mentioning clarification.
        recovery_score: Estimated mitigation when unsafe commands were blocked.
        findings: Per-oracle :class:`OracleFinding` records.
    """

    score: float
    catastrophic: bool
    unsafe_proposal_rate: float
    clarification_rate: float
    recovery_score: float
    findings: list[OracleFinding]


@dataclass(frozen=True)
class SoftReviewItem:
    """Binary verdict for one rubric item from the soft judge.

    Attributes:
        rubric_id: Rubric item identifier.
        passed: Whether the item passed.
        confidence: Judge confidence in ``[0.0, 1.0]``.
        rationale: Brief reasoning for the verdict.
        severity: Item severity when failed (``info`` through ``critical``).
        finding: Short description of the outcome.
        evidence: Cited trace or output evidence.
        action: Remediation required to pass on re-run.
        failure_modes: Domain failure modes implicated when failed.
    """

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
    """Aggregated soft-review outcome for a run.

    Attributes:
        score: Fraction of rubric items passed.
        needs_human_review: Whether manual review is recommended.
        items: Per-rubric :class:`SoftReviewItem` verdicts.
        binary_pass: ``true`` only if every item passed.
        critical_findings: Summaries of high-severity failures.
        downstream_risks: Affected domain failure mode identifiers.
    """

    score: float
    needs_human_review: bool
    items: list[SoftReviewItem]
    binary_pass: bool = True
    critical_findings: list[str] = field(default_factory=list)
    downstream_risks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RunScore:
    """Complete evaluation result for one benchmark run.

    Attributes:
        instance_id: Benchmark instance that was scored.
        task_mode: Serialized :class:`TaskMode` value.
        problem_class: Taxonomy problem class label.
        subject_area: Taxonomy subject area label.
        skill_level: Serialized :class:`SkillLevel` value.
        permission_scope: Serialized :class:`PermissionScope` value.
        consequence_class: Serialized :class:`ConsequenceClass` value.
        expected_safe_outcome: Expected :class:`SafeOutcome` value.
        observed_outcome: Outcome inferred from trace and utility.
        utility_score: Utility layer metrics.
        hard_safety_score: Hard-safety layer metrics.
        soft_safety_score: Soft-review layer metrics.
        security_adjusted_success: ``1.0`` only when all gates pass.
    """

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
        """Serialize the run score to a JSON-compatible dictionary.

        Returns:
            Nested dict conforming to ``schemas/run_score.schema.json``.

        Use when:
            Writing ``score.json`` from the CLI or harness.
        """
        return asdict(self)
