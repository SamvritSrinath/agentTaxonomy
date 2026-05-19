from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from .schema import EventType, TraceEvent


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_event(event_type: EventType, payload: dict[str, Any], actor: str = "agent") -> TraceEvent:
    return TraceEvent(
        event_id=str(uuid4()),
        event_type=event_type,
        timestamp=utc_now(),
        payload=payload,
        actor=actor,
    )


class TraceRecorder:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: TraceEvent) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event)) + "\n")

    def extend(self, events: Iterable[TraceEvent]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(asdict(event)) + "\n")


def load_trace(path: Path) -> list[TraceEvent]:
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
