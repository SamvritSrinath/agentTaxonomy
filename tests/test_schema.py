import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SchemaTests(unittest.TestCase):
    def test_instance_schema_declares_shared_task_modes(self) -> None:
        schema = json.loads((PROJECT_ROOT / "schemas" / "instance.schema.json").read_text(encoding="utf-8"))

        self.assertIn("task_mode", schema["required"])
        self.assertEqual(schema["properties"]["task_mode"]["enum"], ["repo_task", "generative_task"])
        self.assertEqual(schema["properties"]["skill_level"]["enum"], ["beginner", "intermediate", "expert"])
        self.assertEqual(
            schema["properties"]["consequence_class"]["enum"],
            [
                "A_read_only_reversible",
                "B_stateful_locally_reversible",
                "C_externally_consequential",
                "D_catastrophic_irreversible",
            ],
        )

    def test_instance_schema_has_mode_specific_requirements(self) -> None:
        schema = json.loads((PROJECT_ROOT / "schemas" / "instance.schema.json").read_text(encoding="utf-8"))
        branches = schema["allOf"]

        repo_branch = next(
            branch for branch in branches if branch["if"]["properties"]["task_mode"]["const"] == "repo_task"
        )
        generative_branch = next(
            branch for branch in branches if branch["if"]["properties"]["task_mode"]["const"] == "generative_task"
        )

        self.assertIn("repo", repo_branch["then"]["required"])
        self.assertIn("base_commit", repo_branch["then"]["required"])
        self.assertNotIn("prompt_variant", schema["properties"])
        self.assertNotIn("attack_surface", schema["properties"])
        self.assertNotIn("overlay_bundle", schema["properties"])
        self.assertIn("expected_artifacts", generative_branch["then"]["required"])
        self.assertIn("allowed_output_files", generative_branch["then"]["required"])
        self.assertIn("domain_failure_modes", generative_branch["then"]["required"])

    def test_instance_schema_declares_repo_safety_metadata(self) -> None:
        schema = json.loads((PROJECT_ROOT / "schemas" / "instance.schema.json").read_text(encoding="utf-8"))

        self.assertIn("filesystem_cleanup_plan", schema["properties"]["task_variant"]["enum"])
        self.assertIn("confirmation_required", schema["properties"])
        self.assertIn("task_constraints", schema["properties"])
        self.assertIn("expected_repo_outcomes", schema["properties"])
        constraint_schema = schema["properties"]["task_constraints"]["items"]
        outcome_schema = schema["properties"]["expected_repo_outcomes"]["items"]
        self.assertIn("constraint_type", constraint_schema["required"])
        self.assertIn("expected_action", outcome_schema["required"])

    def test_run_score_schema_requires_actionable_soft_review_fields(self) -> None:
        schema = json.loads((PROJECT_ROOT / "schemas" / "run_score.schema.json").read_text(encoding="utf-8"))
        soft_schema = schema["properties"]["soft_safety_score"]
        item_schema = soft_schema["properties"]["items"]["items"]

        self.assertIn("binary_pass", soft_schema["required"])
        self.assertIn("critical_findings", soft_schema["required"])
        self.assertIn("downstream_risks", soft_schema["required"])
        self.assertIn("severity", item_schema["required"])
        self.assertIn("evidence", item_schema["required"])
        self.assertIn("action", item_schema["required"])
        self.assertIn("failure_modes", item_schema["required"])

    def test_run_score_schema_requires_verification_and_gate_fields(self) -> None:
        schema = json.loads((PROJECT_ROOT / "schemas" / "run_score.schema.json").read_text(encoding="utf-8"))

        for field in [
            "verification_tier",
            "correctness_verified_by_execution",
            "security_audit_performed",
            "security_audit_pass",
            "static_blocking_findings_absent",
            "positive_security_verified",
            "unverified_gates",
            "warning_gates",
            "audit_strength",
            "security_audit_meaning",
            "auto_soft_binary_pass",
            "certified_soft_pass",
            "review_status",
            "provisional_security_success",
            "blocking_gates",
            "trace_completeness_score",
            "supply_chain_score",
            "security_gate_verdicts",
            "full_execution_skipped",
        ]:
            self.assertIn(field, schema["required"])
        gate_schema = schema["properties"]["security_gate_verdicts"]["items"]
        self.assertIn("verdict", gate_schema["required"])
        self.assertEqual(schema["properties"]["verification_tier"]["enum"], ["output_only", "static", "smoke", "full"])

    def test_instance_schema_declares_structured_runtime_profiles(self) -> None:
        schema = json.loads((PROJECT_ROOT / "schemas" / "instance.schema.json").read_text(encoding="utf-8"))
        profile_schema = schema["properties"]["runtime_profiles"]["items"]

        self.assertIn("runtime_profiles", schema["properties"])
        self.assertIn("name", profile_schema["required"])
        self.assertEqual(profile_schema["properties"]["name"]["enum"], ["static", "smoke", "full"])

    def test_trace_schema_includes_repo_and_audit_events(self) -> None:
        schema = json.loads((PROJECT_ROOT / "schemas" / "trace_event.schema.json").read_text(encoding="utf-8"))
        event_types = schema["properties"]["event_type"]["enum"]

        self.assertIn("repo_snapshot", event_types)
        self.assertIn("file_read", event_types)
        self.assertIn("supply_chain_enrichment", event_types)
        self.assertIn("approval_requested", event_types)
        self.assertIn("reasoning_summary", event_types)


if __name__ == "__main__":
    unittest.main()
