from agentTaxonomy.deterministic_checks import run_deterministic_checks
from agentTaxonomy.taxonomy import task_by_id


def test_forbidden_path_detection_works() -> None:
    task = task_by_id("api_rate_limiting")
    report = run_deterministic_checks(
        task=task,
        touched_files=[{"path": ".env", "status": "modified"}],
        diff_text="",
        stdout="",
        stderr="",
        telemetry={},
    )
    assert report["forbidden_path_touched"]
    assert not report["deterministic_security_pass"]
