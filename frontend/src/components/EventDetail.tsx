import type { SafetyEvent } from "../api/types";
import { formatDateTime, formatMs } from "../lib/format";
import { DecisionBadge, Empty } from "./ui";

export function EventDetail({ event }: { event: SafetyEvent | undefined }) {
  if (!event) return <Empty>Select a decision to see why DreamGuard made it.</Empty>;
  const { report } = event;
  const faults = event.metadata?.injected_faults;
  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-slate-400">#{event.sequence}</span>
        <DecisionBadge decision={report.decision} />
        <span className="text-slate-300">risk {report.risk_score}</span>
        <span className="text-slate-400">
          {report.checked_rows} rows · {formatMs(report.latency_ms)} · {event.source}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-400">
        <dt>Executed by robot</dt>
        <dd className={event.executed ? "text-emerald-300" : "text-rose-300"}>
          {event.executed ? "yes" : "no (never reached the controller)"}
        </dd>
        <dt>Time</dt>
        <dd>{formatDateTime(event.timestamp)}</dd>
        {Array.isArray(faults) && faults.length > 0 && (
          <>
            <dt>Injected fault</dt>
            <dd className="text-violet-200">{faults.join(", ")}</dd>
          </>
        )}
        {event.error && (
          <>
            <dt>Robot error</dt>
            <dd className="text-rose-300">{event.error}</dd>
          </>
        )}
      </dl>
      {report.findings.length === 0 ? (
        <p className="text-emerald-300">No safety violations.</p>
      ) : (
        <ul className="max-h-64 space-y-1 overflow-y-auto" aria-label="Findings">
          {report.findings.map((finding, index) => (
            <li
              key={`${finding.check}-${finding.arm}-${finding.row}-${finding.joint}-${index}`}
              className={`rounded-md px-2 py-1 ${
                finding.severity === "violation"
                  ? "bg-rose-950/50 text-rose-100"
                  : "bg-amber-950/40 text-amber-100"
              }`}
            >
              <span className="mr-2 font-mono text-xs uppercase opacity-70">{finding.check}</span>
              {finding.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
