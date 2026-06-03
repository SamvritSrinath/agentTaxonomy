from pathlib import Path

from agentTaxonomy.taxonomy import PROMPT_LEVELS, load_taxonomy, validate_taxonomy_files


def test_taxonomy_loads_and_every_task_has_three_prompts() -> None:
    tasks = load_taxonomy()
    assert len(tasks) >= 30
    ids = {task.task_id for task in tasks}
    assert "api_rate_limiting" in ids
    assert "browser_extension_message_passing" in ids

    root = Path(__file__).resolve().parents[1]
    forbidden_prompt_phrases = [
        "security benchmark",
        "taxonomy",
        "skill level",
        "beginner",
        "intermediate",
        "expert",
        "we are evaluating you",
        "hidden test",
        "trap",
        "vulnerability benchmark",
    ]
    for task in tasks:
        for level in PROMPT_LEVELS:
            prompt = task.prompt_path(level, root)
            assert prompt.exists(), prompt
            text = prompt.read_text(encoding="utf-8").lower()
            assert text.strip()
            for phrase in forbidden_prompt_phrases:
                assert phrase not in text


def test_taxonomy_files_validate() -> None:
    report = validate_taxonomy_files()
    assert report["valid"], report
    assert report["task_count"] >= 30
    assert report["prompt_count"] >= 90
