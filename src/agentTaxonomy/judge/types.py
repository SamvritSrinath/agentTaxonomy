"""Shared types for soft-review judges."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..schema import BenchmarkInstance, SoftSafetyScore, TraceEvent


@dataclass(frozen=True)
class HumanReviewOverride:
    """Human adjudication that replaces a single rubric verdict.

    Used when a human reviewer has already decided pass/fail for one rubric
    item and the judge pipeline should honor that decision instead of
    re-grading it heuristically or via the LLM.

    Attributes:
        rubric_id: Catalog identifier of the rubric question being overridden.
        passed: Whether the human reviewer marked the item as passed.
        confidence: Reviewer confidence in ``passed`` (0.0–1.0).
        rationale: Free-text explanation supporting the override.
    """

    rubric_id: str
    passed: bool
    confidence: float
    rationale: str


class SoftJudge(Protocol):
    """Protocol implemented by heuristic and LLM soft-review judges.

    Any class that scores agent traces against an instance's soft-review rubric
    should implement :meth:`evaluate` with this signature so harness code can
    swap backends without changing call sites.

    Use when:
        Typing judge dependencies, writing tests with fakes, or documenting
        the contract that :class:`~agentTaxonomy.judge.heuristic_judge.HeuristicSoftJudge`
        and :class:`~agentTaxonomy.judge.openrouter.OpenRouterJudge` satisfy.
    """

    def evaluate(
        self,
        instance: BenchmarkInstance,
        trace: list[TraceEvent],
        human_overrides: dict[str, HumanReviewOverride] | None = None,
    ) -> SoftSafetyScore:
        """Score a run trace against the instance soft-review rubric.

        Args:
            instance: Benchmark case containing the rubric, metadata, and
                expected safe outcome used for grading context.
            trace: Ordered list of trace events from the agent run.
            human_overrides: Optional map from ``rubric_id`` to human verdicts
                that replace judge output for those items.

        Returns:
            Aggregated soft safety score with per-rubric items, run-level
            ``score``, ``binary_pass``, and review flags.

        Use when:
            Invoking any soft-review backend from the harness, CLI, or tests.
        """
        ...
