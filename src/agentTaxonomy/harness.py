"""High-level benchmark harness for catalog, scoring, and run summarization."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .catalog import build_catalog, validate_distribution, write_catalog
from .judge import HumanReviewOverride, OpenRouterConfig, OpenRouterJudge, SoftJudge
from .schema import BenchmarkCatalog, BenchmarkInstance, RunScore
from .scoring import load_json_report, load_run_report, score_run, summarize_results
from .trace import load_trace


class BenchmarkHarness:
    """Facade over catalog loading, run scoring, and OpenRouter judge construction."""

    def __init__(self, project_root: Path) -> None:
        """Load the benchmark catalog for the given repository root.

        Args:
            project_root: Path to the repository root (parent of ``benchmark/``).

        Use when:
            Constructing the harness from the CLI or integration tests.
        """
        self.project_root = project_root
        self.catalog = build_catalog()

    def validate_catalog(self) -> dict[str, dict[str, int]]:
        """Validate all catalog instances and return label distributions.

        Returns:
            Histogram dict from :func:`~agentTaxonomy.catalog.validate_distribution`.

        Raises:
            ValueError: If any instance fails validation.

        Use when:
            Running ``validate-catalog`` to confirm catalog integrity before scoring.
        """
        self.catalog.validate(self.project_root)
        return validate_distribution(self.catalog)

    def write_catalog(self, output_path: Path | None = None) -> Path:
        """Regenerate ``benchmark/generated/catalog.json`` and split files.

        Args:
            output_path: Optional path for ``catalog.json``.

        Returns:
            Path to the written catalog file.

        Use when:
            Running ``build-catalog`` after editing task definitions.
        """
        return write_catalog(self.project_root, output_path)

    def instance_by_id(self, instance_id: str) -> BenchmarkInstance:
        """Look up a benchmark instance by id.

        Args:
            instance_id: Instance identifier (for example ``cuda_reduction_kernel__expert``).

        Returns:
            Matching :class:`~agentTaxonomy.schema.BenchmarkInstance`.

        Raises:
            KeyError: If no instance with the given id exists.

        Use when:
            Resolving ``--instance-id`` for scoring, judging, or prompt rendering.
        """
        for instance in self.catalog.instances:
            if instance.instance_id == instance_id:
                return instance
        raise KeyError(f"unknown instance_id {instance_id}")

    def score_run(
        self,
        instance_id: str,
        trace_path: Path | None = None,
        *,
        trace_events: list | None = None,
        run_report_path: Path | None = None,
        human_review_path: Path | None = None,
        judge: SoftJudge | None = None,
        verification_tier: str = "output_only",
        audit_report_path: Path | None = None,
        supply_chain_report_path: Path | None = None,
        correctness_verified_by_execution: bool = False,
        full_execution_skipped: bool = False,
        skip_reason: str | None = None,
    ) -> RunScore:
        """Score a run trace for a catalog instance.

        Args:
            instance_id: Benchmark instance to evaluate.
            trace_path: Path to ``trace.jsonl``.
            run_report_path: Optional JSON test report for utility scoring.
            human_review_path: Optional JSON list of human rubric overrides.
            judge: Soft judge implementation; uses heuristic judge when omitted.
            verification_tier: Strongest correctness tier applied (``output_only`` through ``full``).
            audit_report_path: Optional path to static-audit JSON report.
            supply_chain_report_path: Optional path to supply-chain enrichment JSON report.
            correctness_verified_by_execution: Whether utility tests were executed and passed.
            full_execution_skipped: Whether the ``full`` runtime profile was skipped.
            skip_reason: Human-readable reason when full execution was not run.

        Returns:
            Complete :class:`~agentTaxonomy.schema.RunScore`.

        Use when:
            Implementing the CLI ``score-run`` command or programmatic evaluation pipelines.
        """
        instance = self.instance_by_id(instance_id)
        if trace_events is not None:
            trace = trace_events
        elif trace_path is not None:
            trace = load_trace(trace_path) if trace_path.exists() else []
        else:
            raise ValueError("score_run requires trace_path or trace_events")
        run_report = load_run_report(run_report_path)
        audit_report = load_json_report(audit_report_path)
        supply_chain_report = load_json_report(supply_chain_report_path)
        human_review = self._load_human_review(human_review_path)
        return score_run(
            instance,
            trace,
            run_report,
            human_review,
            judge,
            verification_tier=verification_tier,
            audit_report=audit_report,
            supply_chain_report=supply_chain_report,
            correctness_verified_by_execution=correctness_verified_by_execution,
            full_execution_skipped=full_execution_skipped,
            skip_reason=skip_reason,
        )

    def make_openrouter_judge(
        self,
        model: str,
        api_key: str | None = None,
        response_format: str = "json_object",
        api_base: str = "https://openrouter.ai/api/v1/chat/completions",
        app_name: str = "coding-agent-taxonomy",
        app_url: str = "https://example.com/coding-agent-taxonomy",
        supply_chain_report: dict | None = None,
    ) -> OpenRouterJudge:
        """Construct an OpenRouter-backed soft-review judge.

        Args:
            model: OpenRouter model id (for example ``openai/gpt-4o``).
            api_key: API key; defaults to ``OPENROUTER_API_KEY`` environment variable.
            response_format: ``"json_object"`` or ``"json_schema"`` for structured output.
            api_base: OpenRouter chat completions endpoint URL.
            app_name: Application name sent in request headers.
            app_url: Referer URL sent in request headers.

        Returns:
            Configured :class:`~agentTaxonomy.judge.OpenRouterJudge`.

        Raises:
            RuntimeError: If no API key is available.

        Use when:
            Passing ``--judge-model`` to ``score-run`` for production soft-review evaluation.
        """
        api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set and no API key was provided.")
        return OpenRouterJudge(
            OpenRouterConfig(
                api_key=api_key,
                model=model,
                api_base=api_base,
                app_name=app_name,
                app_url=app_url,
                response_format=response_format,
                supply_chain_report=supply_chain_report,
            )
        )

    def summarize_from_paths(self, result_paths: list[Path]) -> dict[str, object]:
        """Load score JSON files and compute aggregate benchmark metrics.

        Args:
            result_paths: Paths to ``score.json`` files from prior ``score-run`` invocations.

        Returns:
            Aggregation dict from :func:`~agentTaxonomy.scoring.summarize_results`.

        Use when:
            Running the CLI ``summarize-runs`` command across multiple experiments.
        """
        results = [self._load_result(path) for path in result_paths]
        return summarize_results(results)

    def _load_result(self, path: Path) -> RunScore:
        """Deserialize a ``score.json`` file into a :class:`~agentTaxonomy.schema.RunScore`."""
        payload = json.loads(path.read_text(encoding="utf-8"))
        return RunScore(
            instance_id=payload["instance_id"],
            task_mode=payload["task_mode"],
            problem_class=payload["problem_class"],
            subject_area=payload["subject_area"],
            skill_level=payload["skill_level"],
            permission_scope=payload["permission_scope"],
            consequence_class=payload["consequence_class"],
            expected_safe_outcome=payload["expected_safe_outcome"],
            observed_outcome=payload["observed_outcome"],
            utility_score=self._utility_from_dict(payload["utility_score"]),
            hard_safety_score=self._hard_from_dict(payload["hard_safety_score"]),
            soft_safety_score=self._soft_from_dict(payload["soft_safety_score"]),
            security_adjusted_success=payload["security_adjusted_success"],
            verification_tier=payload.get("verification_tier", "output_only"),
            correctness_verified_by_execution=payload.get("correctness_verified_by_execution", False),
            security_audit_performed=payload.get("security_audit_performed", False),
            security_audit_pass=payload.get("security_audit_pass", False),
            static_blocking_findings_absent=payload.get(
                "static_blocking_findings_absent",
                payload.get("security_audit_pass", False),
            ),
            positive_security_verified=payload.get("positive_security_verified", False),
            unverified_gates=list(payload.get("unverified_gates", [])),
            warning_gates=list(payload.get("warning_gates", [])),
            audit_strength=payload.get("audit_strength", "none"),
            security_audit_meaning=payload.get("security_audit_meaning", ""),
            auto_soft_binary_pass=payload.get("auto_soft_binary_pass", payload.get("soft_safety_score", {}).get("binary_pass", False)),
            certified_soft_pass=payload.get("certified_soft_pass", False),
            review_status=payload.get("review_status", "certified"),
            provisional_security_success=payload.get("provisional_security_success", 0.0),
            blocking_gates=list(payload.get("blocking_gates", [])),
            trace_completeness_score=payload.get("trace_completeness_score", 0.0),
            supply_chain_score=payload.get("supply_chain_score", 1.0),
            security_gate_verdicts=self._security_gates_from_dict(payload.get("security_gate_verdicts", [])),
            full_execution_skipped=payload.get("full_execution_skipped", False),
            skip_reason=payload.get("skip_reason"),
        )

    def _load_human_review(self, path: Path | None) -> dict[str, HumanReviewOverride] | None:
        """Load human rubric overrides from a JSON file."""
        if path is None:
            return None
        raw_items = json.loads(path.read_text(encoding="utf-8"))
        overrides = {
            item["rubric_id"]: HumanReviewOverride(
                rubric_id=item["rubric_id"],
                passed=item["passed"],
                confidence=item["confidence"],
                rationale=item["rationale"],
            )
            for item in raw_items
        }
        return overrides

    @staticmethod
    def _utility_from_dict(payload: dict[str, object]):
        """Reconstruct :class:`~agentTaxonomy.schema.UtilityScore` from JSON."""
        from .schema import UtilityScore

        return UtilityScore(**payload)

    @staticmethod
    def _hard_from_dict(payload: dict[str, object]):
        """Reconstruct :class:`~agentTaxonomy.schema.HardSafetyScore` from JSON."""
        from .schema import HardSafetyScore, OracleFinding

        findings = [OracleFinding(**item) for item in payload["findings"]]
        return HardSafetyScore(
            score=payload["score"],
            catastrophic=payload["catastrophic"],
            unsafe_proposal_rate=payload["unsafe_proposal_rate"],
            clarification_rate=payload["clarification_rate"],
            recovery_score=payload["recovery_score"],
            findings=findings,
        )

    @staticmethod
    def _soft_from_dict(payload: dict[str, object]):
        """Reconstruct :class:`~agentTaxonomy.schema.SoftSafetyScore` from JSON."""
        from .schema import SoftReviewItem, SoftSafetyScore

        items = [SoftReviewItem(**item) for item in payload["items"]]
        return SoftSafetyScore(
            score=payload["score"],
            needs_human_review=payload["needs_human_review"],
            items=items,
            binary_pass=payload.get("binary_pass", all(item.passed for item in items)),
            critical_findings=list(payload.get("critical_findings", [])),
            downstream_risks=list(payload.get("downstream_risks", [])),
        )

    @staticmethod
    def _security_gates_from_dict(payload: list[dict[str, object]]):
        """Reconstruct :class:`~agentTaxonomy.schema.SecurityGateVerdict` values."""
        from .schema import SecurityGateVerdict

        verdicts: list[SecurityGateVerdict] = []
        for item in payload:
            data = dict(item)
            if "verdict" not in data:
                data["verdict"] = "pass" if data.get("passed") else "fail"
            data.setdefault("positive_evidence", False)
            data.setdefault("checks_run", [])
            verdicts.append(SecurityGateVerdict(**data))
        return verdicts
