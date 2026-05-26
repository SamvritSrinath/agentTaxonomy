"""Tests for OpenRouter repo-task generation and worktree apply."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agentTaxonomy.agents.openrouter_repo_agent import (
    REPO_TASK_SYSTEM_PROMPT,
    _build_repo_model_request,
    _extract_repo_model_content,
    apply_agent_output_to_worktree,
    generate_repo_model_output,
)
from agentTaxonomy.generate import OpenRouterGenerator


class OpenRouterRepoAgentTests(unittest.TestCase):
    def test_build_repo_model_request_disables_tools(self) -> None:
        generator = OpenRouterGenerator(
            MagicMock(model="test/model", api_key="key", base_url="https://example.com", timeout_s=30)
        )
        body = _build_repo_model_request(generator, "do the task", REPO_TASK_SYSTEM_PROMPT)
        self.assertEqual(body["tool_choice"], "none")
        self.assertEqual(body["messages"][0]["role"], "system")

    def test_extract_content_rejects_tool_calls(self) -> None:
        payload = {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": " ",
                        "tool_calls": [{"function": {"name": "View"}}],
                    },
                }
            ]
        }
        with self.assertRaises(RuntimeError) as ctx:
            _extract_repo_model_content(payload)
        self.assertIn("tool calls", str(ctx.exception).lower())

    def test_apply_writes_fenced_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp)
            output_dir = worktree / "out"
            output_dir.mkdir()
            agent_output = output_dir / "agent_output.md"
            agent_output.write_text("```python app.py\nprint('ok')\n```\n", encoding="utf-8")
            result = apply_agent_output_to_worktree(worktree, agent_output, instance=None)
            self.assertEqual(result.applied_files, ["app.py"])
            self.assertEqual((worktree / "app.py").read_text(encoding="utf-8"), "print('ok')\n")

    def test_apply_accepts_allowed_glob_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp)
            output_dir = worktree / "out"
            output_dir.mkdir()
            agent_output = output_dir / "agent_output.md"
            agent_output.write_text("```sql sql/preview_duplicates.sql\nselect 1;\n```\n", encoding="utf-8")
            instance = SimpleNamespace(allowed_output_files=["README.md", "sql/**", "reports/**"])

            result = apply_agent_output_to_worktree(worktree, agent_output, instance=instance)

            self.assertEqual(result.applied_files, ["sql/preview_duplicates.sql"])
            self.assertEqual((worktree / "sql" / "preview_duplicates.sql").read_text(encoding="utf-8"), "select 1;\n")

    def test_apply_rejects_new_file_outside_allowed_glob_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp)
            agent_output = worktree / "agent_output.md"
            agent_output.write_text("```python cleanup_duplicate_users.py\nprint('unsafe')\n```\n", encoding="utf-8")
            instance = SimpleNamespace(allowed_output_files=["README.md", "sql/**", "reports/**"])

            with self.assertRaises(RuntimeError) as ctx:
                apply_agent_output_to_worktree(worktree, agent_output, instance=instance)

            self.assertIn("not_allowed:cleanup_duplicate_users.py", str(ctx.exception))

    def test_apply_raises_when_no_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp)
            agent_output = worktree / "agent_output.md"
            agent_output.write_text("no fenced blocks here\n", encoding="utf-8")
            with self.assertRaises(RuntimeError) as ctx:
                apply_agent_output_to_worktree(worktree, agent_output)
            self.assertIn("did not apply any files", str(ctx.exception))

    def test_generate_repo_model_output_persists_artifacts(self) -> None:
        stub_response = {
            "choices": [{"message": {"content": "```app.py\n# ok\n"}}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            generator = MagicMock(spec=OpenRouterGenerator)
            generator.config = MagicMock(model="stub/model")
            generator._build_request.return_value = {"messages": [], "model": "stub/model"}
            generator._send_request.return_value = stub_response
            with patch("agentTaxonomy.agents.openrouter_repo_agent.config_from_env") as cfg:
                cfg.return_value = MagicMock(model="stub/model")
                result = generate_repo_model_output(
                    prompt_text="task",
                    output_dir=output_dir,
                    model="stub/model",
                    instance_id="test__instance",
                    generator=generator,
                )
            self.assertTrue((output_dir / "request.json").exists())
            self.assertTrue((output_dir / "raw_response.json").exists())
            self.assertIn("app.py", (output_dir / "agent_output.md").read_text(encoding="utf-8"))
            self.assertEqual(result["model"], "stub/model")


if __name__ == "__main__":
    unittest.main()
