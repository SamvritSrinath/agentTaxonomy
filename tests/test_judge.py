import unittest

from agentTaxonomy.catalog import build_catalog
from agentTaxonomy.judge import (
    HeuristicSoftJudge,
    JUDGE_SYSTEM_PROMPT,
    OpenRouterConfig,
    OpenRouterJudge,
    build_openrouter_judge_request,
    parse_judge_response_content,
    render_judge_prompt,
)
from agentTaxonomy.judge.scoring import aggregate_soft_safety_score
from agentTaxonomy.schema import EventType, SoftReviewItem
from agentTaxonomy.trace import new_event


class JudgeTests(unittest.TestCase):
    def _instance(self):
        catalog = build_catalog()
        return next(instance for instance in catalog.instances if instance.instance_id == "cuda_reduction_kernel__expert")

    def _trace(self):
        return [
            new_event(
                EventType.AGENT_PROMPT_RENDERED,
                {"instance_id": "cuda_reduction_kernel__expert", "model": "moonshotai/kimi-k2.5"},
                actor="harness",
            ),
            new_event(
                EventType.FINAL_RESPONSE,
                {"message": "Here is a CUDA reduction implementation with tests and nvcc build commands."},
            ),
        ]

    def test_render_judge_prompt_includes_rubric_and_domain_context(self) -> None:
        prompt = render_judge_prompt(self._instance(), self._trace())
        prompt_lower = prompt.lower()

        self.assertIn("evaluate the coding-agent run", prompt_lower)
        self.assertIn("pass_condition", prompt_lower)
        self.assertIn("domain_failure_modes", prompt_lower)
        self.assertIn("supply-chain", prompt_lower)
        self.assertIn("g0 trace_completeness", prompt_lower)
        self.assertIn("g9 approval_and_halt_behavior", prompt_lower)
        self.assertIn("insufficient evidence", prompt_lower)
        self.assertIn('"problem_class": "Cuda Reduction Kernel"', prompt)
        self.assertIn("out_of_bounds_global_memory_access", prompt)
        self.assertIn("emit exactly these rubric_ids", prompt_lower)

    def test_judge_system_prompt_is_fail_closed_and_binary(self) -> None:
        system_lower = JUDGE_SYSTEM_PROMPT.lower()
        self.assertIn("fail closed", system_lower)
        self.assertIn("binary", system_lower)
        self.assertIn("do not reward effort", system_lower)
        self.assertIn("insufficient evidence", system_lower)

    def test_openrouter_request_matches_prompt_modules(self) -> None:
        instance = self._instance()
        trace = self._trace()
        config = OpenRouterConfig(api_key="test", model="openai/gpt-5.5", response_format="json_schema")
        request = build_openrouter_judge_request(instance, trace, config)

        self.assertEqual(request["messages"][0]["content"], JUDGE_SYSTEM_PROMPT)
        self.assertEqual(request["messages"][1]["content"], render_judge_prompt(instance, trace))

        schema = request["response_format"]["json_schema"]["schema"]
        item_schema = schema["properties"]["items"]["items"]
        self.assertIn("binary_pass", schema["required"])
        self.assertIn("critical_findings", schema["required"])
        self.assertIn("downstream_risks", schema["required"])
        self.assertIn("severity", item_schema["required"])
        self.assertIn("evidence", item_schema["required"])
        self.assertIn("action", item_schema["required"])
        self.assertIn("failure_modes", item_schema["required"])

    def test_openrouter_judge_build_request_alias(self) -> None:
        judge = OpenRouterJudge(OpenRouterConfig(api_key="test", model="openai/gpt-5.5", response_format="json_schema"))
        request = judge.build_request(self._instance(), self._trace())
        self.assertIn("messages", request)

    def test_parse_judge_response_content_handles_fenced_json(self) -> None:
        payload = {
            "score": 0.5,
            "binary_pass": False,
            "needs_human_review": True,
            "critical_findings": [],
            "downstream_risks": [],
            "items": [
                {
                    "rubric_id": "problem_classification",
                    "passed": True,
                    "severity": "info",
                    "confidence": 0.9,
                    "finding": "ok",
                    "evidence": "spark",
                    "action": "",
                    "failure_modes": [],
                    "rationale": "ok",
                }
            ],
        }
        raw = "Analysis first.\n\n```json\n" + __import__("json").dumps(payload) + "\n```"
        parsed = parse_judge_response_content(raw)
        self.assertEqual(parsed["binary_pass"], False)
        self.assertEqual(len(parsed["items"]), 1)

    def test_parse_judge_response_content_handles_bare_json(self) -> None:
        payload = {
            "score": 1.0,
            "binary_pass": True,
            "needs_human_review": False,
            "critical_findings": [],
            "downstream_risks": [],
            "items": [],
        }
        parsed = parse_judge_response_content(__import__("json").dumps(payload))
        self.assertTrue(parsed["binary_pass"])

    def test_aggregate_recomputes_score_from_items(self) -> None:
        items = [
            SoftReviewItem(
                rubric_id="a",
                passed=True,
                confidence=0.9,
                rationale="ok",
            ),
            SoftReviewItem(
                rubric_id="b",
                passed=False,
                confidence=0.9,
                rationale="fail",
                severity="high",
                finding="bad",
            ),
        ]
        score = aggregate_soft_safety_score(items)
        self.assertAlmostEqual(score.score, 0.5)
        self.assertFalse(score.binary_pass)

    def test_heuristic_judge_fails_closed_with_actionable_findings(self) -> None:
        score = HeuristicSoftJudge().evaluate(self._instance(), self._trace())
        failed_items = [item for item in score.items if not item.passed]

        self.assertFalse(score.binary_pass)
        self.assertTrue(score.needs_human_review)
        self.assertTrue(failed_items)
        self.assertTrue(all(item.finding for item in failed_items))
        self.assertTrue(all(item.action for item in failed_items))


if __name__ == "__main__":
    unittest.main()
