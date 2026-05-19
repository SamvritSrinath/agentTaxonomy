import unittest

from agentTaxonomy.catalog import build_catalog
from agentTaxonomy.judge import (
    HeuristicSoftJudge,
    OpenRouterConfig,
    OpenRouterJudge,
    parse_judge_response_content,
    render_judge_prompt,
)
from agentTaxonomy.schema import EventType
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

    def test_render_judge_prompt_is_adversarial_binary_and_actionable(self) -> None:
        prompt = render_judge_prompt(self._instance(), self._trace())
        prompt_lower = prompt.lower()

        self.assertIn("adversarial evaluation task", prompt_lower)
        self.assertIn("fail closed", prompt_lower)
        self.assertIn("binary pass or fail", prompt_lower)
        self.assertIn("actionable remediation", prompt_lower)
        self.assertIn("supply chain", prompt_lower)
        self.assertIn("buffer overflow", prompt_lower)
        self.assertIn("unauthorized actions", prompt_lower)
        self.assertIn('"problem_class": "Cuda Reduction Kernel"', prompt)
        self.assertIn("out_of_bounds_global_memory_access", prompt)
        self.assertIn("failure_modes", prompt)
        self.assertNotIn("Return JSON with fields: score, needs_human_review, items[].", prompt)

    def test_openrouter_json_schema_requires_actionable_binary_fields(self) -> None:
        judge = OpenRouterJudge(OpenRouterConfig(api_key="test", model="openai/gpt-5.5", response_format="json_schema"))
        request = judge._build_request(self._instance(), self._trace())
        system_prompt = request["messages"][0]["content"]
        response_format = request["response_format"]
        schema = response_format["json_schema"]["schema"]
        item_schema = schema["properties"]["items"]["items"]

        self.assertIn("adversarial security and utility evaluator", system_prompt)
        self.assertIn("Do not praise effort", system_prompt)
        self.assertIn("binary_pass", schema["required"])
        self.assertIn("critical_findings", schema["required"])
        self.assertIn("downstream_risks", schema["required"])
        self.assertIn("severity", item_schema["required"])
        self.assertIn("evidence", item_schema["required"])
        self.assertIn("action", item_schema["required"])
        self.assertIn("failure_modes", item_schema["required"])

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
