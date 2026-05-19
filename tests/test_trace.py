from pathlib import Path
import tempfile
import unittest

from agentTaxonomy.schema import EventType
from agentTaxonomy.trace import TraceRecorder, load_trace, new_event


class TraceTests(unittest.TestCase):
    def test_trace_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            trace_path = Path(tmp_dir) / "trace.jsonl"
            recorder = TraceRecorder(trace_path)
            recorder.extend(
                [
                    new_event(EventType.PROMPT_CONTEXT_LOAD, {"instance_id": "demo"}),
                    new_event(EventType.COMMAND_PROPOSED, {"command": "pytest -q"}),
                    new_event(EventType.FINAL_RESPONSE, {"message": "completed safely"}),
                ]
            )

            events = load_trace(trace_path)
            self.assertEqual(len(events), 3)
            self.assertEqual(events[0].event_type, EventType.PROMPT_CONTEXT_LOAD)
            self.assertEqual(events[1].payload["command"], "pytest -q")

    def test_new_security_trace_events_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            trace_path = Path(tmp_dir) / "trace.jsonl"
            recorder = TraceRecorder(trace_path)
            recorder.extend(
                [
                    new_event(EventType.REPO_SNAPSHOT, {"phase": "before", "repo_sha256": "abc"}),
                    new_event(EventType.FILE_READ, {"path": "README.md"}),
                    new_event(EventType.SUPPLY_CHAIN_ENRICHMENT, {"supply_chain_path": "supply_chain.json"}),
                    new_event(EventType.APPROVAL_REQUESTED, {"reason": "destructive delete"}),
                    new_event(EventType.REASONING_SUMMARY, {"summary": "halted for approval"}),
                ]
            )

            events = load_trace(trace_path)
            self.assertEqual(events[0].event_type, EventType.REPO_SNAPSHOT)
            self.assertEqual(events[2].event_type, EventType.SUPPLY_CHAIN_ENRICHMENT)
            self.assertEqual(events[4].event_type, EventType.REASONING_SUMMARY)


if __name__ == "__main__":
    unittest.main()
