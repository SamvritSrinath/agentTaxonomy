"""Trace event construction and JSONL persistence for agent runs."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from .schema import EventType, TraceEvent


def utc_now() -> str:
    """Return the current UTC timestamp in ISO-8601 format.

    Returns:
        An ISO-8601 timestamp string with timezone information.

    Use when:
        Creating trace events that require a consistent, timezone-aware clock.
    """
    return datetime.now(UTC).isoformat()


def new_event(event_type: EventType, payload: dict[str, Any], actor: str = "agent") -> TraceEvent:
    """Construct a new trace event with a unique identifier and timestamp.

    Args:
        event_type: Semantic category of the event (for example ``final_response``).
        payload: Event-specific data recorded for scoring and auditing.
        actor: Entity that produced the event. Defaults to ``"agent"``.

    Returns:
        A :class:`~agentTaxonomy.schema.TraceEvent` ready to append to a trace.

    Use when:
        Recording harness, agent, or oracle activity during a benchmark run.
    """
    return TraceEvent(
        event_id=str(uuid4()),
        event_type=event_type,
        timestamp=utc_now(),
        payload=payload,
        actor=actor,
    )


class TraceRecorder:
    """Append-only JSONL writer for benchmark run traces.

    Use when:
        Persisting events incrementally during generation or interactive agent runs.
    """

    def __init__(self, path: Path) -> None:
        """Initialize the recorder for a target JSONL file.

        Args:
            path: Destination ``trace.jsonl`` path. Parent directories are created.

        Use when:
            Starting a new run directory before events are emitted.
        """
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: TraceEvent) -> None:
        """Append a single event as one JSON line.

        Args:
            event: Trace event to persist.

        Use when:
            Logging individual steps such as prompt rendering or command proposals.
        """
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event)) + "\n")

    def extend(self, events: Iterable[TraceEvent]) -> None:
        """Append multiple events in order.

        Args:
            events: Iterable of trace events to persist.

        Use when:
            Flushing a batch of related events (for example final response after generation).
        """
        with self.path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(asdict(event)) + "\n")


def load_trace(path: Path) -> list[TraceEvent]:
    """Load a trace from a JSONL file produced by :class:`TraceRecorder`.

    Args:
        path: Path to ``trace.jsonl``.

    Returns:
        Ordered list of parsed :class:`~agentTaxonomy.schema.TraceEvent` objects.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        json.JSONDecodeError: If a line is not valid JSON.
        KeyError: If a required event field is missing.

    Use when:
        Scoring a run via :func:`~agentTaxonomy.scoring.score_run` or the CLI ``score-run`` command.
    """
    events: list[TraceEvent] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        data = json.loads(raw_line)
        events.append(
            TraceEvent(
                event_id=data["event_id"],
                event_type=EventType(data["event_type"]),
                timestamp=data["timestamp"],
                actor=data.get("actor", "agent"),
                payload=data["payload"],
            )
        )
    return events
