from pathlib import Path
import json
import tempfile
import unittest

from agentTaxonomy.generate import (
    OpenRouterGenerationConfig,
    extract_message_content,
    generate_run,
)
from agentTaxonomy.schema import EventType
from agentTaxonomy.trace import load_trace


class FakeGenerator:
    def _build_request(self, prompt: str, system_prompt: str):
        return {
            "model": "moonshotai/kimi-k2.5",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        }

    def generate(self, prompt: str, system_prompt: str):
        return {
            "choices": [
                {
                    "message": {
                        "content": "Generated CUDA solution."
                    }
                }
            ]
        }


class GenerateTests(unittest.TestCase):
    def test_extract_message_content(self) -> None:
        payload = {"choices": [{"message": {"content": "hello"}}]}
        self.assertEqual(extract_message_content(payload), "hello")

    def test_generate_run_writes_outputs_and_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            prompt_file = root / "expert.md"
            output_dir = root / "run"
            prompt_file.write_text("Implement a CUDA reduction kernel.", encoding="utf-8")

            result = generate_run(
                prompt_file=prompt_file,
                output_dir=output_dir,
                config=OpenRouterGenerationConfig(api_key="test", model="moonshotai/kimi-k2.5"),
                system_prompt="You are a coding agent.",
                instance_id="cuda_reduction_kernel__expert",
                generator=FakeGenerator(),
            )

            self.assertTrue(Path(result.request_path).exists())
            self.assertTrue(Path(result.raw_response_path).exists())
            self.assertEqual(Path(result.agent_output_path).read_text(encoding="utf-8"), "Generated CUDA solution.\n")
            raw = json.loads(Path(result.raw_response_path).read_text(encoding="utf-8"))
            self.assertEqual(raw["choices"][0]["message"]["content"], "Generated CUDA solution.")

            trace = load_trace(Path(result.trace_path))
            self.assertEqual([event.event_type for event in trace], [
                EventType.AGENT_PROMPT_RENDERED,
                EventType.AGENT_OUTPUT_RECEIVED,
                EventType.FINAL_RESPONSE,
            ])
            self.assertEqual(trace[0].payload["instance_id"], "cuda_reduction_kernel__expert")
            self.assertEqual(trace[1].payload["model"], "moonshotai/kimi-k2.5")
            self.assertEqual(trace[2].payload["message"], "Generated CUDA solution.")


if __name__ == "__main__":
    unittest.main()
