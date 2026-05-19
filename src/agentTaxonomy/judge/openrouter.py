"""OpenRouter-backed LLM soft-review judge."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from ..generate import extract_message_content
from ..schema import BenchmarkInstance, SoftReviewItem, SoftSafetyScore, TraceEvent
from .prompts import JUDGE_SYSTEM_PROMPT, render_judge_user_prompt
from .response_schema import SOFT_REVIEW_JSON_SCHEMA, parse_judge_response_content
from .scoring import (
    aggregate_soft_safety_score,
    order_rubric_items,
    soft_review_item_from_override,
)
from .types import HumanReviewOverride, SoftJudge


@dataclass(frozen=True)
class OpenRouterConfig:
    """Connection settings for the OpenRouter chat-completions API.

    Attributes:
        api_key: Bearer token for OpenRouter authentication.
        model: Model id passed to the ``model`` field (e.g. provider/model name).
        api_base: Chat-completions endpoint URL.
        app_name: Value for the ``X-OpenRouter-Title`` header.
        app_url: Value for the ``HTTP-Referer`` header.
        timeout_seconds: HTTP read timeout for judge requests.
        response_format: ``"json_object"`` for generic JSON mode or
            ``"json_schema"`` to attach :data:`~agentTaxonomy.judge.response_schema.SOFT_REVIEW_JSON_SCHEMA`.
    """

    api_key: str
    model: str
    api_base: str = "https://openrouter.ai/api/v1/chat/completions"
    app_name: str = "unsafe-autonomy-bench"
    app_url: str = "https://example.com/unsafe-autonomy-bench"
    timeout_seconds: float = 90.0
    response_format: str = "json_object"


def build_openrouter_judge_request(
    instance: BenchmarkInstance,
    trace: list[TraceEvent],
    config: OpenRouterConfig,
) -> dict[str, object]:
    """Build the full OpenRouter chat-completions payload for a soft-review call.

    Combines :data:`~agentTaxonomy.judge.prompts.JUDGE_SYSTEM_PROMPT`, the
    rendered user prompt, deterministic sampling settings, and JSON response
    formatting.

    Args:
        instance: Benchmark case to grade.
        trace: Trace events from the agent run.
        config: API credentials, model id, and response format options.

    Returns:
        Request body suitable for POSTing to OpenRouter's chat-completions API.

    Use when:
        Inspecting or replaying judge requests in tests, debugging prompt
        issues, or implementing custom HTTP clients that call the same API.
    """
    body: dict[str, object] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": render_judge_user_prompt(instance, trace)},
        ],
        "temperature": 0,
        "seed": 7,
        "response_format": {"type": "json_object"},
    }
    if config.response_format == "json_schema":
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "unsafe_autonomy_soft_review",
                "strict": True,
                "schema": SOFT_REVIEW_JSON_SCHEMA,
            },
        }
    return body


def soft_review_item_from_payload(item: dict[str, object]) -> SoftReviewItem:
    """Convert a parsed LLM rubric item dict into a :class:`~agentTaxonomy.schema.SoftReviewItem`.

    Normalizes optional fields with safe defaults so partially populated model
    output still produces valid catalog items.

    Args:
        item: One element from the parsed judge JSON ``items`` array.

    Returns:
        Typed soft review item ready for ordering and aggregation.

    Use when:
        Mapping OpenRouter judge responses after
        :func:`~agentTaxonomy.judge.response_schema.parse_judge_response_content`.
    """
    return SoftReviewItem(
        rubric_id=str(item["rubric_id"]),
        passed=bool(item["passed"]),
        confidence=float(item["confidence"]),
        rationale=str(item.get("rationale", item.get("finding", ""))),
        severity=str(item.get("severity", "info")),
        finding=str(item.get("finding", "")),
        evidence=str(item.get("evidence", "")),
        action=str(item.get("action", "")),
        failure_modes=[str(mode) for mode in item.get("failure_modes", [])],
    )


class OpenRouterJudge:
    """Adversarial soft-review judge backed by an OpenRouter chat model.

    Sends instance metadata, rubric, and trace to an LLM, parses structured
    JSON verdicts, applies optional human overrides, and aggregates a
    :class:`~agentTaxonomy.schema.SoftSafetyScore`.

    Use when:
        Production or research evaluation where rubric items need
        evidence-backed LLM grading rather than keyword heuristics.
    """

    def __init__(self, config: OpenRouterConfig) -> None:
        """Store OpenRouter connection settings for subsequent evaluations.

        Args:
            config: API key, model, timeouts, and response-format options.
        """
        self.config = config

    def evaluate(
        self,
        instance: BenchmarkInstance,
        trace: list[TraceEvent],
        human_overrides: dict[str, HumanReviewOverride] | None = None,
    ) -> SoftSafetyScore:
        """Call OpenRouter and aggregate rubric verdicts into a soft safety score.

        Builds the request, posts to OpenRouter, parses JSON rubric items,
        merges human overrides, orders items in catalog sequence, and recomputes
        run-level metrics from per-item verdicts.

        Args:
            instance: Benchmark case containing the soft-review rubric.
            trace: Trace events from the agent run under review.
            human_overrides: Optional per-rubric human verdicts that replace
                LLM output for matching ``rubric_id`` values.

        Returns:
            Aggregated soft safety score with ordered rubric items.

        Raises:
            RuntimeError: If the HTTP request fails (network error or non-2xx
                status). The error message includes response body text when
                available.
            ValueError: If the model response cannot be parsed as rubric JSON
                (propagated from :func:`~agentTaxonomy.judge.response_schema.parse_judge_response_content`).

        Use when:
            Scoring benchmark runs in production pipelines that have an
            OpenRouter API key and model configured.
        """
        request_body = build_openrouter_judge_request(instance, trace, self.config)
        response_payload = self._send_request(request_body)
        raw_content = extract_message_content(response_payload)
        parsed = parse_judge_response_content(raw_content)

        items_by_id = {
            str(item["rubric_id"]): soft_review_item_from_payload(item)
            for item in parsed["items"]  # type: ignore[union-attr]
        }
        if human_overrides:
            for rubric_id, override in human_overrides.items():
                items_by_id[rubric_id] = soft_review_item_from_override(override)

        ordered_items = order_rubric_items(instance.soft_review_rubric.questions, items_by_id)
        return aggregate_soft_safety_score(
            ordered_items,
            needs_human_review=bool(parsed.get("needs_human_review", False)),
            critical_findings=[str(item) for item in parsed.get("critical_findings", [])] or None,
            downstream_risks=[str(item) for item in parsed.get("downstream_risks", [])] or None,
        )

    def build_request(self, instance: BenchmarkInstance, trace: list[TraceEvent]) -> dict[str, object]:
        """Return the OpenRouter request body (for tests and debugging).

        Args:
            instance: Benchmark case to grade.
            trace: Trace events from the agent run.

        Returns:
            Chat-completions request dict that would be sent by :meth:`evaluate`.

        Use when:
            Unit tests, golden-file checks, or CLI commands that print the
            judge payload without calling the network.
        """
        return build_openrouter_judge_request(instance, trace, self.config)

    def _send_request(self, body: dict[str, object]) -> dict[str, object]:
        """POST the judge payload to OpenRouter and return the parsed JSON body.

        Args:
            body: Chat-completions request produced by
                :func:`build_openrouter_judge_request`.

        Returns:
            Parsed JSON response from OpenRouter (chat completion envelope).

        Raises:
            RuntimeError: On HTTP errors or URL/network failures.
        """
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self.config.api_base,
            data=data,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": self.config.app_url,
                "X-OpenRouter-Title": self.config.app_name,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenRouter judge request failed with HTTP {exc.code}: {details}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenRouter judge request failed: {exc}") from exc
