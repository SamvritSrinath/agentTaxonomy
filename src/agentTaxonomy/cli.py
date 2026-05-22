"""Command-line interface for catalog, generation, scoring, and doc utilities."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .harness import BenchmarkHarness


def _project_root() -> Path:
    """Return the repository root directory (parent of ``src/``)."""
    return Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    """Construct the ``catt`` / ``agentTaxonomy.cli`` argument parser.

    Returns:
        Configured :class:`argparse.ArgumentParser` with subcommands for catalog
        build, run generation, scoring, auditing, and repo-task execution.
    """
    parser = argparse.ArgumentParser(description="Coding Agent Taxonomy (CaT) toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("build-catalog", help="Generate the benchmark catalog and split files.")
    subparsers.add_parser("validate-catalog", help="Validate the benchmark catalog and print distribution stats.")

    generate_parser = subparsers.add_parser("generate-run", help="Generate an agent response for a prompt file with OpenRouter.")
    generate_parser.add_argument("--prompt-file", required=True, help="Path to the agent-facing prompt file.")
    generate_parser.add_argument("--model", required=True, help="OpenRouter model id, for example moonshotai/kimi-k2.5.")
    generate_parser.add_argument("--output-dir", help="Directory for request.json, raw_response.json, agent_output.md, and trace.jsonl.")
    generate_parser.add_argument("--instance-id", help="Optional benchmark instance id to include in trace metadata.")
    generate_parser.add_argument("--system-prompt", help="System prompt text. Defaults to a coding-agent instruction.")
    generate_parser.add_argument("--system-prompt-file", help="Path to a file containing the system prompt.")
    generate_parser.add_argument("--api-base", default="https://openrouter.ai/api/v1/chat/completions")
    generate_parser.add_argument("--api-key", help="OpenRouter API key. Defaults to OPENROUTER_API_KEY.")
    generate_parser.add_argument("--app-name", default="coding-agent-taxonomy")
    generate_parser.add_argument("--app-url", default="https://example.com/coding-agent-taxonomy")
    generate_parser.add_argument("--temperature", type=float, default=0.2)
    generate_parser.add_argument("--max-tokens", type=int, default=8000)
    generate_parser.add_argument("--timeout-seconds", type=float, default=120.0)

    score_parser = subparsers.add_parser("score-run", help="Score a run from trace and optional run report.")
    score_parser.add_argument("--instance-id", required=True)
    score_parser.add_argument("--trace", required=True)
    score_parser.add_argument("--run-report")
    score_parser.add_argument("--human-review")
    score_parser.add_argument("--audit-report")
    score_parser.add_argument("--supply-chain-report")
    score_parser.add_argument("--verification-tier", choices=["output_only", "static", "smoke", "full"], default="output_only")
    score_parser.add_argument("--correctness-verified-by-execution", action="store_true")
    score_parser.add_argument("--full-execution-skipped", action="store_true")
    score_parser.add_argument("--skip-reason")
    score_parser.add_argument("--output")
    score_parser.add_argument("--judge-model")
    score_parser.add_argument("--judge-response-format", choices=["json_object", "json_schema"], default="json_object")
    score_parser.add_argument("--judge-api-base", default="https://openrouter.ai/api/v1/chat/completions")
    score_parser.add_argument("--judge-app-name", default="coding-agent-taxonomy")
    score_parser.add_argument("--judge-app-url", default="https://example.com/coding-agent-taxonomy")

    prompt_parser = subparsers.add_parser(
        "render-judge-prompt",
        help="Render the soft-review user prompt for an instance and trace.",
    )
    prompt_parser.add_argument("--instance-id", required=True)
    prompt_parser.add_argument("--trace", required=True)

    request_parser = subparsers.add_parser(
        "render-judge-request",
        help="Render the full OpenRouter judge request JSON (system prompt, schema, trace).",
    )
    request_parser.add_argument("--instance-id", required=True)
    request_parser.add_argument("--trace", required=True)
    request_parser.add_argument("--judge-model", default="openai/gpt-4o")
    request_parser.add_argument(
        "--judge-response-format",
        choices=["json_object", "json_schema"],
        default="json_schema",
    )

    summary_parser = subparsers.add_parser("summarize-runs", help="Aggregate run score JSON files.")
    summary_parser.add_argument("results", nargs="+")

    audit_parser = subparsers.add_parser("static-audit", help="Run deterministic static/security audit.")
    audit_parser.add_argument("--instance-id", required=True)
    audit_source = audit_parser.add_mutually_exclusive_group(required=True)
    audit_source.add_argument("--artifact-dir")
    audit_source.add_argument("--artifact")
    audit_parser.add_argument("--output", required=True)
    audit_parser.add_argument(
        "--extract-first",
        action="store_true",
        help="When auditing a single markdown artifact, extract fenced blocks into <artifact-dir>/extracted first.",
    )

    extract_parser = subparsers.add_parser(
        "extract-artifacts",
        help="Extract fenced code blocks from agent_output.md into an artifact directory.",
    )
    extract_parser.add_argument("--artifact", required=True, help="Markdown file to extract from.")
    extract_parser.add_argument("--output-dir", required=True, help="Directory for extracted files.")
    extract_parser.add_argument("--manifest", help="Optional path for extract_manifest.json.")

    supply_parser = subparsers.add_parser("enrich-supply-chain", help="Extract supply-chain evidence.")
    supply_parser.add_argument("--artifact-dir", required=True)
    supply_parser.add_argument("--output", required=True)

    repo_parser = subparsers.add_parser("run-repo-task", help="Run a repo task with snapshot-wrapper instrumentation.")
    repo_parser.add_argument("--instance-id", required=True)
    repo_parser.add_argument("--repo", required=True)
    repo_parser.add_argument("--agent-cmd", required=True)
    repo_parser.add_argument("--profile", choices=["static", "smoke", "full"], default="static")
    repo_parser.add_argument("--output-dir", required=True)
    repo_parser.add_argument("--sandbox-profile", help="Optional sandbox profile name for command shims.")
    repo_parser.add_argument("--docker-sandbox", action="store_true", help="Run the agent command in a Docker container with network disabled.")

    db_parser = subparsers.add_parser("db", help="Manage the local research workbench database.")
    db_subparsers = db_parser.add_subparsers(dest="db_command", required=True)

    db_init = db_subparsers.add_parser("init", help="Create workbench database tables.")
    db_init.add_argument("--database-url")

    db_reset = db_subparsers.add_parser("reset", help="Drop and recreate local workbench database tables.")
    db_reset.add_argument("--database-url")

    db_migrate = db_subparsers.add_parser("migrate", help="Apply local workbench schema creation/migrations.")
    db_migrate.add_argument("--database-url")

    db_catalog = db_subparsers.add_parser("ingest-catalog", help="Index a generated benchmark catalog JSON file.")
    db_catalog.add_argument("catalog", nargs="?", default="benchmark/generated/catalog.json")
    db_catalog.add_argument("--database-url")

    db_run = db_subparsers.add_parser("ingest-run", help="Index one raw run directory.")
    db_run.add_argument("run_dir")
    db_run.add_argument("--database-url")
    db_run.add_argument("--new-ingest-version", action="store_true")

    db_eval = db_subparsers.add_parser("ingest-evaluation", help="Create an additional evaluation view for a run directory.")
    db_eval.add_argument("run_dir")
    db_eval.add_argument("--evidence-condition", choices=["code_only", "code_plus_trace"], required=True)
    db_eval.add_argument("--database-url")

    db_rescore = db_subparsers.add_parser("rescore-run", help="Create a new evaluation for an indexed run id.")
    db_rescore.add_argument("run_id")
    db_rescore.add_argument("--evidence-condition", choices=["code_only", "code_plus_trace"], required=True)
    db_rescore.add_argument("--database-url")

    db_runs = db_subparsers.add_parser("ingest-runs", help="Index every run directory below a root.")
    db_runs.add_argument("runs_root", nargs="?", default="runs")
    db_runs.add_argument("--database-url")
    db_runs.add_argument("--new-ingest-version", action="store_true")

    db_bootstrap = db_subparsers.add_parser("bootstrap", help="Bootstrap catalog, prompts, templates, and runs.")
    db_bootstrap.add_argument("--database-url")
    db_bootstrap.add_argument("--rebuild-catalog", action="store_true")
    db_bootstrap.add_argument("--catalog-path", default="benchmark/generated/catalog.json")
    db_bootstrap.add_argument("--runs-root", default="runs")

    for name, help_text in [
        ("export-runs", "Export runs to CSV or Parquet."),
        ("export-findings", "Export findings to CSV or Parquet."),
        ("export-evaluations", "Export evaluations to CSV or Parquet."),
        ("export-wide", "Export one wide analysis table to CSV or Parquet."),
    ]:
        export_parser = db_subparsers.add_parser(name, help=help_text)
        export_parser.add_argument("output")
        export_parser.add_argument("--database-url")

    annotate_parser = subparsers.add_parser("annotate", help="Manage human annotation assignments and agreement.")
    annotate_subparsers = annotate_parser.add_subparsers(dest="annotate_command", required=True)
    annotate_assign = annotate_subparsers.add_parser("assign", help="Assign runs to annotators.")
    annotate_assign.add_argument("--annotators", required=True, help="Comma-separated annotator ids.")
    annotate_assign.add_argument("--run-id", action="append", dest="run_ids", help="Run id to assign; repeatable.")
    annotate_assign.add_argument("--experiment-id")
    annotate_assign.add_argument("--limit", type=int)
    annotate_assign.add_argument("--database-url")
    annotate_agreement = annotate_subparsers.add_parser("agreement", help="Compute annotation agreement and flag disagreements.")
    annotate_agreement.add_argument("--experiment-id")
    annotate_agreement.add_argument("--database-url")

    adjudicate_parser = subparsers.add_parser("adjudicate", help="Export adjudicated labels.")
    adjudicate_subparsers = adjudicate_parser.add_subparsers(dest="adjudicate_command", required=True)
    adjudicate_export = adjudicate_subparsers.add_parser("export", help="Export adjudications to CSV or Parquet.")
    adjudicate_export.add_argument("output")
    adjudicate_export.add_argument("--database-url")

    experiment_parser = subparsers.add_parser("experiment", help="Create, run, and summarize experiment matrices.")
    experiment_subparsers = experiment_parser.add_subparsers(dest="experiment_command", required=True)
    experiment_create = experiment_subparsers.add_parser("create", help="Store a YAML experiment design.")
    experiment_create.add_argument("--design", required=True)
    experiment_create.add_argument("--database-url")
    experiment_run = experiment_subparsers.add_parser("run", help="Run a YAML experiment design.")
    experiment_run.add_argument("--design", required=True)
    experiment_run.add_argument("--output-root", default="runs/experiments")
    experiment_run.add_argument("--database-url")
    experiment_summarize = experiment_subparsers.add_parser("summarize", help="Export an experiment analysis CSV.")
    experiment_summarize.add_argument("--output", default="analysis.csv")
    experiment_summarize.add_argument("--database-url")

    web_parser = subparsers.add_parser("web", help="Run the local FastAPI research workbench backend.")
    web_parser.add_argument("--host", default="127.0.0.1")
    web_parser.add_argument("--port", type=int, default=8080)
    web_parser.add_argument("--database-url")
    web_parser.add_argument(
        "--reload",
        action="store_true",
        help="Reload the API when source files change (recommended for local dev).",
    )

    return parser


def main_deprecated(argv: list[str] | None = None) -> int:
    """Deprecated ``uab`` entry point; forwards to :func:`main` with a warning."""
    print(
        "warning: `uab` is deprecated; use `catt` (Coding Agent Taxonomy Tool) instead.",
        file=sys.stderr,
    )
    return main(argv)


def main(argv: list[str] | None = None) -> int:
    """Run a CLI subcommand and return a process exit code.

    Args:
        argv: Command-line arguments excluding the program name. Defaults to
            ``sys.argv[1:]`` when ``None``.

    Returns:
        Process exit code (``0`` on success, non-zero on failure).
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    harness = BenchmarkHarness(_project_root())

    if args.command == "build-catalog":
        output_path = harness.write_catalog()
        print(output_path)
        return 0

    if args.command == "validate-catalog":
        print(json.dumps(harness.validate_catalog(), indent=2))
        return 0

    if args.command == "generate-run":
        from .generate import DEFAULT_SYSTEM_PROMPT, config_from_env, generate_run

        if args.system_prompt and args.system_prompt_file:
            parser.error("--system-prompt and --system-prompt-file are mutually exclusive")
        prompt_file = Path(args.prompt_file)
        output_dir = Path(args.output_dir) if args.output_dir else _default_generation_output_dir(prompt_file, args.model)
        system_prompt = DEFAULT_SYSTEM_PROMPT
        if args.system_prompt:
            system_prompt = args.system_prompt
        elif args.system_prompt_file:
            system_prompt = Path(args.system_prompt_file).read_text(encoding="utf-8")
        config = config_from_env(
            model=args.model,
            api_key=args.api_key,
            api_base=args.api_base,
            app_name=args.app_name,
            app_url=args.app_url,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout_seconds=args.timeout_seconds,
        )
        result = generate_run(
            prompt_file=prompt_file,
            output_dir=output_dir,
            config=config,
            system_prompt=system_prompt,
            instance_id=args.instance_id,
        )
        print(
            json.dumps(
                {
                    "model": result.model,
                    "prompt_file": result.prompt_file,
                    "output_dir": result.output_dir,
                    "request_path": result.request_path,
                    "raw_response_path": result.raw_response_path,
                    "agent_output_path": result.agent_output_path,
                    "trace_path": result.trace_path,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "score-run":
        judge = None
        if args.judge_model:
            judge = harness.make_openrouter_judge(
                model=args.judge_model,
                response_format=args.judge_response_format,
                api_base=args.judge_api_base,
                app_name=args.judge_app_name,
                app_url=args.judge_app_url,
            )
        result = harness.score_run(
            instance_id=args.instance_id,
            trace_path=Path(args.trace),
            run_report_path=Path(args.run_report) if args.run_report else None,
            human_review_path=Path(args.human_review) if args.human_review else None,
            judge=judge,
            verification_tier=args.verification_tier,
            audit_report_path=Path(args.audit_report) if args.audit_report else None,
            supply_chain_report_path=Path(args.supply_chain_report) if args.supply_chain_report else None,
            correctness_verified_by_execution=args.correctness_verified_by_execution,
            full_execution_skipped=args.full_execution_skipped,
            skip_reason=args.skip_reason,
        )
        payload = json.dumps(result.to_dict(), indent=2)
        if args.output:
            Path(args.output).write_text(payload + "\n", encoding="utf-8")
        else:
            print(payload)
        return 0

    if args.command == "render-judge-prompt":
        from .judge import render_judge_prompt
        from .trace import load_trace

        instance = harness.instance_by_id(args.instance_id)
        trace = load_trace(Path(args.trace))
        print(render_judge_prompt(instance, trace))
        return 0

    if args.command == "render-judge-request":
        from .judge import OpenRouterConfig, build_openrouter_judge_request
        from .trace import load_trace

        instance = harness.instance_by_id(args.instance_id)
        trace = load_trace(Path(args.trace))
        request = build_openrouter_judge_request(
            instance,
            trace,
            OpenRouterConfig(
                api_key="REDACTED",
                model=args.judge_model,
                response_format=args.judge_response_format,
            ),
        )
        print(json.dumps(request, indent=2))
        return 0

    if args.command == "summarize-runs":
        result = harness.summarize_from_paths([Path(path) for path in args.results])
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "extract-artifacts":
        from .artifact_extract import write_extracted_artifacts

        manifest = write_extracted_artifacts(
            Path(args.artifact),
            Path(args.output_dir),
            Path(args.manifest) if args.manifest else None,
        )
        print(json.dumps(manifest, indent=2))
        return 0

    if args.command == "static-audit":
        from .audit import write_static_audit
        from .artifact_extract import write_extracted_artifacts

        instance = harness.instance_by_id(args.instance_id)
        artifact_dir = Path(args.artifact_dir) if args.artifact_dir else None
        artifact = Path(args.artifact) if args.artifact else None
        if args.extract_first and artifact is not None:
            extracted_dir = artifact.parent / "extracted"
            write_extracted_artifacts(artifact, extracted_dir, extracted_dir / "extract_manifest.json")
            artifact_dir = extracted_dir
            artifact = None
        report = write_static_audit(
            instance,
            Path(args.output),
            artifact_dir=artifact_dir,
            artifact=artifact,
        )
        print(json.dumps(report, indent=2))
        return 0

    if args.command == "enrich-supply-chain":
        from .supply_chain import write_supply_chain_report

        report = write_supply_chain_report(Path(args.artifact_dir), Path(args.output))
        print(json.dumps(report, indent=2))
        return 0

    if args.command == "run-repo-task":
        from dataclasses import asdict

        from .repo_runner import run_repo_task

        result = run_repo_task(
            instance=harness.instance_by_id(args.instance_id),
            repo=Path(args.repo),
            agent_cmd=args.agent_cmd,
            profile_name=args.profile,
            output_dir=Path(args.output_dir),
            sandbox_profile_name=args.sandbox_profile,
            docker_sandbox=args.docker_sandbox,
        )
        print(json.dumps(asdict(result), indent=2))
        return 0

    if args.command == "db":
        return _handle_db_command(args)

    if args.command == "annotate":
        return _handle_annotate_command(args)

    if args.command == "adjudicate":
        return _handle_adjudicate_command(args)

    if args.command == "experiment":
        return _handle_experiment_command(args)

    if args.command == "web":
        import os

        from .env import load_local_env, project_root

        load_local_env()
        if args.database_url:
            os.environ["DATABASE_URL"] = args.database_url
        import uvicorn

        reload_kwargs: dict[str, object] = {}
        if args.reload:
            # Watch only application source — not runs/, .cat-data/, or web/ builds.
            # Otherwise artifact extract during judge/generate triggers full reloads and freezes the UI.
            reload_kwargs["reload_dirs"] = [str(project_root() / "src")]
            reload_kwargs["reload_excludes"] = [
                "runs/*",
                ".cat-data/*",
                ".uab-data/*",
                "web/node_modules/*",
                "node_modules/*",
                "benchmark/generated/*",
            ]
        uvicorn.run(
            "agentTaxonomy.web.api:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            **reload_kwargs,
        )
        return 0

    parser.error(f"unknown command {args.command}")
    return 2


def _handle_db_command(args: argparse.Namespace) -> int:
    """Execute a ``uab db`` subcommand."""
    if args.db_command == "init":
        from .db import init_database

        init_database(args.database_url)
        print(json.dumps({"status": "ok", "command": args.db_command}, indent=2))
        return 0

    if args.db_command == "migrate":
        from .db import migrate_database

        migrate_database(args.database_url)
        print(json.dumps({"status": "ok", "command": "migrate"}, indent=2))
        return 0

    if args.db_command == "reset":
        from .db import reset_database

        reset_database(args.database_url)
        print(json.dumps({"status": "ok", "command": "reset"}, indent=2))
        return 0

    if args.db_command == "ingest-catalog":
        from .db import ingest_catalog

        result = ingest_catalog(Path(args.catalog), database_url=args.database_url)
        print(json.dumps(result.__dict__, indent=2))
        return 0

    if args.db_command == "ingest-run":
        from .db import ingest_run

        result = ingest_run(
            Path(args.run_dir),
            database_url=args.database_url,
            new_ingest_version=args.new_ingest_version,
        )
        print(json.dumps(result.__dict__, indent=2))
        return 0

    if args.db_command == "ingest-runs":
        from .db import ingest_runs

        results = ingest_runs(
            Path(args.runs_root),
            database_url=args.database_url,
            new_ingest_version=args.new_ingest_version,
        )
        print(json.dumps([result.__dict__ for result in results], indent=2))
        return 0

    if args.db_command == "ingest-evaluation":
        from .db import ingest_evaluation

        result = ingest_evaluation(
            Path(args.run_dir),
            evidence_condition=args.evidence_condition,
            database_url=args.database_url,
        )
        print(json.dumps(result.__dict__, indent=2))
        return 0

    if args.db_command == "rescore-run":
        from .db import rescore_run

        result = rescore_run(
            args.run_id,
            evidence_condition=args.evidence_condition,
            database_url=args.database_url,
        )
        print(json.dumps(result.__dict__, indent=2))
        return 0

    if args.db_command == "export-runs":
        from .db.exports import export_runs

        print(export_runs(Path(args.output), database_url=args.database_url))
        return 0

    if args.db_command == "export-findings":
        from .db.exports import export_findings

        print(export_findings(Path(args.output), database_url=args.database_url))
        return 0

    if args.db_command == "export-evaluations":
        from .db.exports import export_evaluations

        print(export_evaluations(Path(args.output), database_url=args.database_url))
        return 0

    if args.db_command == "export-wide":
        from .db.exports import export_wide

        print(export_wide(Path(args.output), database_url=args.database_url))
        return 0

    if args.db_command == "bootstrap":
        from .db.bootstrap import format_bootstrap_stdout, run_bootstrap

        summary = run_bootstrap(
            rebuild_catalog=args.rebuild_catalog,
            catalog_path=Path(args.catalog_path),
            runs_root=Path(args.runs_root),
            database_url=args.database_url,
        )
        print(format_bootstrap_stdout(summary))
        return 0

    raise ValueError(f"unknown db command {args.db_command}")


def _handle_annotate_command(args: argparse.Namespace) -> int:
    """Execute a ``uab annotate`` subcommand."""
    from .db.services import assign_annotations, compute_annotation_agreement
    from .db.session import session_scope

    if args.annotate_command == "assign":
        annotators = [item.strip() for item in args.annotators.split(",") if item.strip()]
        with session_scope(args.database_url) as session:
            rows = assign_annotations(
                session,
                annotators=annotators,
                run_ids=args.run_ids,
                experiment_id=args.experiment_id,
                limit=args.limit,
            )
        print(json.dumps({"assigned": len(rows), "annotations": rows}, indent=2))
        return 0

    if args.annotate_command == "agreement":
        with session_scope(args.database_url) as session:
            result = compute_annotation_agreement(session, experiment_id=args.experiment_id)
        print(json.dumps(result, indent=2))
        return 0

    raise ValueError(f"unknown annotate command {args.annotate_command}")


def _handle_adjudicate_command(args: argparse.Namespace) -> int:
    """Execute a ``uab adjudicate`` subcommand."""
    if args.adjudicate_command == "export":
        from .db.exports import export_adjudications

        print(export_adjudications(Path(args.output), database_url=args.database_url))
        return 0
    raise ValueError(f"unknown adjudicate command {args.adjudicate_command}")


def _handle_experiment_command(args: argparse.Namespace) -> int:
    """Execute a ``uab experiment`` subcommand."""
    from .experiments import create_experiment_from_yaml, run_experiment_from_yaml, summarize_experiment

    if args.experiment_command == "create":
        result = create_experiment_from_yaml(Path(args.design), database_url=args.database_url)
        print(json.dumps(result, indent=2))
        return 0
    if args.experiment_command == "run":
        result = run_experiment_from_yaml(
            Path(args.design),
            output_root=Path(args.output_root),
            database_url=args.database_url,
        )
        print(json.dumps(result, indent=2))
        return 0
    if args.experiment_command == "summarize":
        print(summarize_experiment(Path(args.output), database_url=args.database_url))
        return 0
    raise ValueError(f"unknown experiment command {args.experiment_command}")


def _default_generation_output_dir(prompt_file: Path, model: str) -> Path:
    """Derive a default ``runs/<prompt>/<model>/`` output path for generation.

    Args:
        prompt_file: Source prompt file path.
        model: OpenRouter model id (slugified for the directory name).

    Returns:
        Default output directory under ``runs/``.
    """
    prompt_stem = prompt_file.stem or "prompt"
    model_slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", model).strip("_") or "model"
    return Path("runs") / prompt_stem / model_slug


if __name__ == "__main__":
    raise SystemExit(main())
