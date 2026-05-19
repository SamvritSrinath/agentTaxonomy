from __future__ import annotations

import json
import os
from pathlib import Path

from .catalog import build_catalog, validate_distribution, write_catalog
from .judge import HumanReviewOverride, OpenRouterConfig, OpenRouterJudge, SoftJudge
from .schema import BenchmarkCatalog, BenchmarkInstance, RunScore
from .scoring import load_run_report, score_run, summarize_results
from .trace import load_trace


class BenchmarkHarness:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.catalog = build_catalog()

    def validate_catalog(self) -> dict[str, dict[str, int]]:
        self.catalog.validate(self.project_root)
        return validate_distribution(self.catalog)

    def write_catalog(self, output_path: Path | None = None) -> Path:
        return write_catalog(self.project_root, output_path)

    def instance_by_id(self, instance_id: str) -> BenchmarkInstance:
        for instance in self.catalog.instances:
            if instance.instance_id == instance_id:
                return instance
        raise KeyError(f"unknown instance_id {instance_id}")

    def score_run(
        self,
        instance_id: str,
        trace_path: Path,
        run_report_path: Path | None = None,
        human_review_path: Path | None = None,
        judge: SoftJudge | None = None,
    ) -> RunScore:
        instance = self.instance_by_id(instance_id)
        trace = load_trace(trace_path)
        run_report = load_run_report(run_report_path)
        human_review = self._load_human_review(human_review_path)
        return score_run(instance, trace, run_report, human_review, judge)

    def make_openrouter_judge(
        self,
        model: str,
        api_key: str | None = None,
        response_format: str = "json_object",
        api_base: str = "https://openrouter.ai/api/v1/chat/completions",
        app_name: str = "unsafe-autonomy-bench",
        app_url: str = "https://example.com/unsafe-autonomy-bench",
    ) -> OpenRouterJudge:
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
            )
        )

    def summarize_from_paths(self, result_paths: list[Path]) -> dict[str, object]:
        results = [self._load_result(path) for path in result_paths]
        return summarize_results(results)

    def _load_result(self, path: Path) -> RunScore:
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
        )

    def _load_human_review(self, path: Path | None) -> dict[str, HumanReviewOverride] | None:
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
        from .schema import UtilityScore

        return UtilityScore(**payload)

    @staticmethod
    def _hard_from_dict(payload: dict[str, object]):
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
