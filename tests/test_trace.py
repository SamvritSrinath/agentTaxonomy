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


if __name__ == "__main__":
    unittest.main()
