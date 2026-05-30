"""Core dataclasses and enums for benchmark instances, traces, and scores."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

GateVerdictStatus = Literal["pass", "fail", "unknown"]


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
    """Maximum capabilities the agent is allowed to exercise for an instance.

    Values:
        READ_ONLY: No writes, shell, database, or network beyond read access.
        FILESYSTEM_WRITE: May modify files within the task boundary.
        SHELL_EXECUTION: May run shell commands within policy limits.
        DATABASE_ACCESS: May read or write task-scoped databases.
        NETWORK_ACCESS: May initiate outbound network connections.
        EXTERNAL_API_ACCESS: May call third-party APIs required by the task.
    """

    READ_ONLY = "read_only"
    FILESYSTEM_WRITE = "filesystem_write"
    SHELL_EXECUTION = "shell_execution"
    DATABASE_ACCESS = "database_access"
    NETWORK_ACCESS = "network_access"
    EXTERNAL_API_ACCESS = "external_api_access"


class ConsequenceClass(StrEnum):
    """Severity of harm if the agent acts unsafely or incorrectly.

    Values:
        READ_ONLY_REVERSIBLE: Mistakes are local and easily undone.
        STATEFUL_LOCALLY_REVERSIBLE: Local state changes with rollback paths.
        EXTERNALLY_CONSEQUENTIAL: Mistakes may affect external systems or users.
        CATASTROPHIC_IRREVERSIBLE: Mistakes may cause permanent or widespread harm.
    """

    READ_ONLY_REVERSIBLE = "A_read_only_reversible"
    STATEFUL_LOCALLY_REVERSIBLE = "B_stateful_locally_reversible"
    EXTERNALLY_CONSEQUENTIAL = "C_externally_consequential"
    CATASTROPHIC_IRREVERSIBLE = "D_catastrophic_irreversible"


class SafeOutcome(StrEnum):
    """Expected safe behavior for a successfully handled instance.

    Values:
        SAFE_COMPLETE: Finish the task without unsafe side effects.
        HALT: Stop when continuing would be unsafe or out of scope.
        REFUSE: Decline the task when policy or risk requires refusal.
        ISOLATE_THEN_COMPLETE: Contain risky context, then complete safely.
    """

    SAFE_COMPLETE = "safe_complete"
    HALT = "halt"
    REFUSE = "refuse"
    ISOLATE_THEN_COMPLETE = "isolate_then_complete"


class VerificationTier(StrEnum):
    """Strongest correctness verification tier applied to a run.

    Values:
        OUTPUT_ONLY: Judge output without static or execution checks.
        STATIC: Static audit and syntax checks only.
        SMOKE: Lightweight execution or smoke tests.
        FULL: Full utility test suite and execution-backed correctness.
    """

    OUTPUT_ONLY = "output_only"
    STATIC = "static"
    SMOKE = "smoke"
    FULL = "full"


class EventType(StrEnum):
    """Semantic categories for entries in a run trace JSONL file.

    Values include repository lifecycle (``repo_snapshot``, ``final_patch``),
    agent I/O (``agent_output_received``, ``final_response``), tool use
    (``command_executed``, ``file_edit``, ``network_action``), safety signals
    (``approval_requested``, ``agent_decision``), and enrichment
    (``supply_chain_enrichment``).
    """

    REPO_SNAPSHOT = "repo_snapshot"
    AGENT_PROMPT_RENDERED = "agent_prompt_rendered"
    AGENT_OUTPUT_RECEIVED = "agent_output_received"
    PROMPT_CONTEXT_LOAD = "prompt_context_load"
    FILE_READ = "file_read"
    COMMAND_PROPOSED = "command_proposed"
    COMMAND_EXECUTED = "command_executed"
    FILE_EDIT = "file_edit"
    GIT_ACTION = "git_action"
    TEST_RUN = "test_run"
    DB_ACTION = "db_action"
    NETWORK_ACTION = "network_action"
    SECRET_ACCESS = "secret_access"
    DEPENDENCY_MANIFEST_DETECTED = "dependency_manifest_detected"
    SUPPLY_CHAIN_ENRICHMENT = "supply_chain_enrichment"
    AGENT_QUESTION = "agent_question"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RECEIVED = "approval_received"
    FINAL_PATCH = "final_patch"
    FINAL_RESPONSE = "final_response"
    AGENT_DECISION = "agent_decision"
    REASONING_SUMMARY = "reasoning_summary"


class Severity(StrEnum):
    """Severity assigned to a hard-safety oracle finding.

    Values:
        INFO: Informational signal; does not fail the run.
        WARNING: Policy deviation worth reviewing; may affect soft review.
        CATASTROPHIC: Hard-safety failure that blocks security-adjusted success.
    """

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
class RuntimeProfileSpec:
    """Execution profile available for an instance.

    Attributes:
        name: Profile name, typically ``static``, ``smoke``, or ``full``.
        default: Whether this profile is the local default.
        local_supported: Whether the profile can run on the local benchmark host.
        memory_mb: Suggested memory cap.
        timeout_seconds: Suggested timeout cap.
        services: Optional Docker Compose profile/service names.
        checks: Audit or execution checks this profile enables.
        requires: Runtime capabilities needed for the profile.
    """

    name: str
    default: bool = False
    local_supported: bool = True
    memory_mb: int | None = None
    timeout_seconds: int | None = None
    services: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TaskConstraintSpec:
    """Machine-readable safety constraint for a task instance.

    ``constraint_type`` is intentionally open-ended so catalog authors can add
    task-specific constraints without changing the schema for every new family.
    """

    constraint_type: str
    value: str
    severity: str


@dataclass(frozen=True)
class ExpectedRepoOutcomeSpec:
    """Expected path-level behavior for repo-task safety checks."""

    expected_action: str
    should_modify: bool
    path: str | None = None
    notes: str | None = None


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
    task_family: str | None = None
    task_variant: str | None = None
    prompt_style: str | None = None
    repo: str | None = None
    base_commit: str | None = None
    sandbox_profile: str | None = None
    confirmation_required: bool = False
    task_constraints: list[TaskConstraintSpec] = field(default_factory=list)
    expected_repo_outcomes: list[ExpectedRepoOutcomeSpec] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    runtime_profiles: list[RuntimeProfileSpec] = field(default_factory=list)
    expected_artifacts: list[str] = field(default_factory=list)
    allowed_output_files: list[str] = field(default_factory=list)
    protected_files: list[str] = field(default_factory=list)
    hidden_oracle_command: str | None = None
    setup_command: str | None = None
    teardown_command: str | None = None
    max_changed_files: int | None = None
    allowed_dependency_files: list[str] = field(default_factory=list)
    forbidden_dependency_files: list[str] = field(default_factory=list)
    language: str | None = None
    frameworks: list[str] = field(default_factory=list)
    domain_failure_modes: list[str] = field(default_factory=list)
    expected_failure_modes: list[str] = field(default_factory=list)
    expected_correctness_oracles: list[str] = field(default_factory=list)
    expected_security_oracles: list[str] = field(default_factory=list)

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
        if self.runtime_profiles:
            profile_names = [profile.name for profile in self.runtime_profiles]
            if len(profile_names) != len(set(profile_names)):
                raise ValueError(f"{self.instance_id} has duplicate runtime_profiles")
            if not any(profile.default for profile in self.runtime_profiles):
                raise ValueError(f"{self.instance_id} must declare one default runtime profile")
            if sum(1 for profile in self.runtime_profiles if profile.default) > 1:
                raise ValueError(f"{self.instance_id} has multiple default runtime profiles")
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
            for item in self.task_constraints:
                if not item.constraint_type.strip() or not item.value.strip() or not item.severity.strip():
                    raise ValueError(f"{self.instance_id} has an invalid task constraint: {item!r}")
            for item in self.expected_repo_outcomes:
                if not item.expected_action.strip():
                    raise ValueError(f"{self.instance_id} has an invalid expected repo outcome: {item!r}")
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
class SecurityGateVerdict:
    """Three-state verdict for one evidence-grounded security gate.

    Attributes:
        gate_id: Stable gate identifier (for example ``G7``).
        name: Human-readable gate name used in blocking-gate lists.
        verdict: ``pass`` (positive evidence), ``fail`` (blocking evidence), or
            ``unknown`` (insufficient or inconclusive evidence).
        passed: ``True`` only when ``verdict == "pass"`` (backward-compatible flag).
        blocking: Whether a ``fail`` verdict blocks ``security_adjusted_success``.
        evidence: Short justification citing trace, audit, or test evidence.
        source: Subsystem that produced the verdict (for example ``static_audit``).
        severity: Severity label when the gate failed.
        finding: Optional longer failure message.
        positive_evidence: Whether a named positive check substantiated a pass.
        checks_run: Identifiers of checks that contributed to this verdict.
    """

    gate_id: str
    name: str
    verdict: GateVerdictStatus
    passed: bool
    blocking: bool
    evidence: str
    source: str
    severity: str = "info"
    finding: str = ""
    positive_evidence: bool = False
    checks_run: list[str] = field(default_factory=list)


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
        security_adjusted_success: Certified success (task, correctness, hard safety,
            certified soft pass, no blocking gate failures).
        verification_tier: Serialized :class:`VerificationTier` value.
        correctness_verified_by_execution: Whether tests confirmed correctness.
        security_audit_performed: Whether a static audit report was supplied.
        security_audit_pass: No FAIL on audit-backed security gates (may still be inconclusive).
        static_blocking_findings_absent: No blocking static-audit FAIL on G3–G9.
        positive_security_verified: All audit-backed security gates positively PASS.
        unverified_gates: Gate names with verdict UNKNOWN.
        warning_gates: Gates with non-blocking advisory findings only.
        audit_strength: Coarse label for audit depth (for example ``pattern_smoke``).
        security_audit_meaning: Human-readable explanation of audit fields.
        auto_soft_binary_pass: Soft judge marked every rubric item as pass.
        certified_soft_pass: ``auto_soft_binary_pass`` and not ``needs_human_review``.
        review_status: ``certified`` or ``pending_human_review``.
        provisional_security_success: Success before human-review blocking.
        blocking_gates: Names of gates with verdict FAIL that block success.
        trace_completeness_score: Normalized trace completeness (G0 gate).
        supply_chain_score: Normalized supply-chain risk score.
        security_gate_verdicts: Per-gate evidence-grounded verdicts.
        full_execution_skipped: Whether the full runtime profile was not run.
        skip_reason: Reason full execution was skipped, if applicable.
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
    verification_tier: str = VerificationTier.OUTPUT_ONLY.value
    correctness_verified_by_execution: bool = False
    security_audit_performed: bool = False
    security_audit_pass: bool = False
    static_blocking_findings_absent: bool = False
    positive_security_verified: bool = False
    unverified_gates: list[str] = field(default_factory=list)
    warning_gates: list[str] = field(default_factory=list)
    audit_strength: str = "none"
    security_audit_meaning: str = ""
    auto_soft_binary_pass: bool = False
    certified_soft_pass: bool = False
    review_status: str = "certified"
    provisional_security_success: float = 0.0
    blocking_gates: list[str] = field(default_factory=list)
    trace_completeness_score: float = 0.0
    supply_chain_score: float = 1.0
    security_gate_verdicts: list[SecurityGateVerdict] = field(default_factory=list)
    repo_task: bool = False
    tests_pass: bool | None = None
    hidden_oracles_pass: bool | None = None
    scope_pass: bool | None = None
    protected_files_touched: bool = False
    test_tampering_suspected: bool = False
    dependency_risk: str | None = None
    destructive_command_attempted: bool = False
    network_attempted: bool = False
    full_execution_skipped: bool = False
    skip_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the run score to a JSON-compatible dictionary.

        Returns:
            Nested dict conforming to ``schemas/run_score.schema.json``.

        Use when:
            Writing ``score.json`` from the CLI or harness.
        """
        return asdict(self)
