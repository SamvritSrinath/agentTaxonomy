"""Offline keyword-based soft-review judge."""

from __future__ import annotations

from ..schema import BenchmarkInstance, SoftSafetyScore, TraceEvent
from .heuristics import evaluate_rubric_heuristic
from .scoring import aggregate_soft_safety_score, soft_review_item_from_override
from .trace_context import build_trace_context
from .types import HumanReviewOverride, SoftJudge


class HeuristicSoftJudge:
    """Local soft-review judge for development, CI smoke tests, and offline scoring.

    Grades each rubric item with registered keyword heuristics in
    :mod:`agentTaxonomy.judge.heuristics`. Unregistered rubric ids fail closed.
    Production scoring should use
    :class:`~agentTaxonomy.judge.openrouter.OpenRouterJudge` so task-specific
    rubric items receive evidence-backed LLM verdicts.

    Use when:
        Running the benchmark without an API key, in CI smoke tests, or when
        approximate pass/fail signal is sufficient.
    """

    def evaluate(
        self,
        instance: BenchmarkInstance,
        trace: list[TraceEvent],
        human_overrides: dict[str, HumanReviewOverride] | None = None,
    ) -> SoftSafetyScore:
        """Score a trace with registered keyword heuristics.

        Builds a :class:`~agentTaxonomy.judge.trace_context.TraceContext` once,
        evaluates each rubric question (honoring human overrides), and
        aggregates run-level metrics.

        Args:
            instance: Benchmark case containing the soft-review rubric.
            trace: Trace events from the agent run.
            human_overrides: Optional map of human verdicts that skip heuristic
                grading for specific ``rubric_id`` values.

        Returns:
            Aggregated soft safety score with one item per rubric question.

        Use when:
            Offline evaluation, local development, or CI pipelines that must not
            call external LLM APIs.
        """
        human_overrides = human_overrides or {}
        ctx = build_trace_context(trace)
        items = []
        for question in instance.soft_review_rubric.questions:
            if question.rubric_id in human_overrides:
                items.append(soft_review_item_from_override(human_overrides[question.rubric_id]))
                continue
            items.append(evaluate_rubric_heuristic(question, instance, ctx))
        return aggregate_soft_safety_score(items)
