"""Normalized trace views used by heuristic rubric evaluators."""

from __future__ import annotations

from dataclasses import dataclass

from ..schema import TraceEvent


@dataclass(frozen=True)
class TraceContext:
    """Lower-cased text slices extracted once per evaluation.

    Caches normalized strings derived from a trace so keyword heuristics can
    scan consistent fields without re-parsing events on every rubric item.

    Attributes:
        trace_text: Concatenation of all event payloads (lowercased), joined
            by newlines.
        action_text: Same as ``trace_text`` but excludes
            ``prompt_context_load`` events (agent actions only).
        final_response_text: Space-joined ``message`` fields from
            ``final_response`` events (lowercased).
        decision_text: Space-joined ``decision`` fields from
            ``agent_decision`` events (lowercased).
    """

    trace_text: str
    action_text: str
    final_response_text: str
    decision_text: str


def build_trace_context(trace: list[TraceEvent]) -> TraceContext:
    """Build normalized trace text fields for keyword heuristics.

    Flattens trace payloads into four searchable strings used by offline
    rubric evaluators in :mod:`agentTaxonomy.judge.heuristics`.

    Args:
        trace: Ordered trace events from a single agent run.

    Returns:
        Immutable context with lowercased text slices for heuristic matching.

    Use when:
        Running :class:`~agentTaxonomy.judge.heuristic_judge.HeuristicSoftJudge`
        or any custom evaluator that reuses the shared keyword helpers.
    """
    trace_text = "\n".join(str(event.payload) for event in trace).lower()
    action_text = "\n".join(
        str(event.payload)
        for event in trace
        if event.event_type.value not in {"prompt_context_load"}
    ).lower()
    final_response_text = " ".join(
        str(event.payload.get("message", ""))
        for event in trace
        if event.event_type.value == "final_response"
    ).lower()
    decision_text = " ".join(
        str(event.payload.get("decision", ""))
        for event in trace
        if event.event_type.value == "agent_decision"
    ).lower()
    return TraceContext(
        trace_text=trace_text,
        action_text=action_text,
        final_response_text=final_response_text,
        decision_text=decision_text,
    )
