"""Command-line interface for catalog, generation, scoring, and doc utilities."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .harness import BenchmarkHarness


def _project_root() -> Path:
    """Return the repository root directory (parent of ``src/``)."""
    return Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    """Construct the ``uab`` / ``agentTaxonomy.cli`` argument parser.

    Returns:
        Configured :class:`argparse.ArgumentParser` with subcommands for catalog
        build, run generation, scoring, auditing, and repo-task execution.
    """
    parser = argparse.ArgumentParser(description="Unsafe autonomy benchmark toolkit")
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
    generate_parser.add_argument("--app-name", default="unsafe-autonomy-bench")
    generate_parser.add_argument("--app-url", default="https://example.com/unsafe-autonomy-bench")
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
    score_parser.add_argument("--judge-app-name", default="unsafe-autonomy-bench")
    score_parser.add_argument("--judge-app-url", default="https://example.com/unsafe-autonomy-bench")

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

    return parser


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
        )
        print(json.dumps(asdict(result), indent=2))
        return 0

    parser.error(f"unknown command {args.command}")
    return 2


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
