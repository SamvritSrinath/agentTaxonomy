"""Unsafe Autonomy Bench — Python API for benchmark catalog and run evaluation.

The ``agentTaxonomy`` package provides:

- Catalog generation from task definitions on disk
- Agent run generation and trace capture (OpenRouter)
- Multi-layer scoring: utility, hard safety, and soft review
- CLI entry points for local and CI workflows

Subpackages
-----------

catalog
    Build and validate ``benchmark/generated/catalog.json``.
cli
    Command-line interface (``uab`` or ``python -m agentTaxonomy.cli``).
generate
    OpenRouter-backed agent generation and artifact capture.
harness
    :class:`~agentTaxonomy.harness.BenchmarkHarness` for orchestration.
judge
    Soft-review judges (heuristic baseline and OpenRouter LLM judge).
schema
    Dataclasses and enums for instances, traces, rubrics, and scores.
scoring
    :func:`~agentTaxonomy.scoring.score_run` and related metrics.
trace
    Trace event construction and JSONL I/O.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
