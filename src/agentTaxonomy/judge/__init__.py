"""Soft-review judges for safety and utility rubrics.

This package implements binary rubric grading over agent traces and generated output.
Two backends are provided:

- :class:`~agentTaxonomy.judge.heuristic_judge.HeuristicSoftJudge` — keyword heuristics for
  development and CI smoke tests
- :class:`~agentTaxonomy.judge.openrouter.OpenRouterJudge` — LLM judge for production evaluation

Modules
-------

prompts
    System and user prompt construction for the LLM judge.
response_schema
    JSON schema and response parsing.
scoring
    Aggregation of per-rubric items into :class:`~agentTaxonomy.schema.SoftSafetyScore`.
heuristics
    Registered offline evaluators per ``rubric_id``.
heuristic_judge
    :class:`~agentTaxonomy.judge.heuristic_judge.HeuristicSoftJudge`.
openrouter
    :class:`~agentTaxonomy.judge.openrouter.OpenRouterJudge` and request builders.

Scoring contract
----------------

- Each rubric item is graded **pass** or **fail** with cited evidence.
- ``score`` and ``binary_pass`` are **recomputed** from items after parsing judge output.
- ``critical_findings`` and ``downstream_risks`` summarize high-severity failures.
- ``needs_human_review`` is set when confidence is low or the judge requests review.
"""

from .heuristic_judge import HeuristicSoftJudge
from .openrouter import OpenRouterConfig, OpenRouterJudge, build_openrouter_judge_request
from .prompts import JUDGE_SYSTEM_PROMPT, render_judge_prompt, render_judge_user_prompt
from .response_schema import SOFT_REVIEW_JSON_SCHEMA, parse_judge_response_content
from .scoring import aggregate_soft_safety_score
from .types import HumanReviewOverride, SoftJudge

__all__ = [
    "aggregate_soft_safety_score",
    "HeuristicSoftJudge",
    "HumanReviewOverride",
    "JUDGE_SYSTEM_PROMPT",
    "OpenRouterConfig",
    "OpenRouterJudge",
    "SOFT_REVIEW_JSON_SCHEMA",
    "SoftJudge",
    "build_openrouter_judge_request",
    "parse_judge_response_content",
    "render_judge_prompt",
    "render_judge_user_prompt",
]
