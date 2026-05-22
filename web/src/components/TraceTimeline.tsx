import type { TraceEvent } from "../api/types";

/**
 * Props for the trace timeline component.
 */
export interface TraceTimelineProps {
  /** Ordered trace events for the selected run. */
  events: TraceEvent[];
  /** Currently selected trace event ids used as annotation evidence. */
  selectedEventIds: string[];
  /** Callback fired when a trace event evidence selection changes. */
  onToggleEvent: (eventId: string) => void;
}

/**
 * Render tool, command, sandbox, and final-output events as a compact timeline.
 *
 * @param props - Timeline inputs.
 * @returns Timeline panel.
 */
export function TraceTimeline({ events, selectedEventIds, onToggleEvent }: TraceTimelineProps) {
  return (
    <section className="panel">
      <h2>Trace</h2>
      <ol className="timeline">
        {events.map((event) => (
          <li key={event.id} className={selectedEventIds.includes(event.id) ? "selected-row" : ""}>
            <button className="text-button" onClick={() => onToggleEvent(event.id)}>
              <span className="timeline-type">{event.event_type}</span>
              <span>{event.summary ?? event.actor ?? "event"}</span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
