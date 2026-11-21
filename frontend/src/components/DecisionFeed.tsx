import type { SafetyEvent } from "../api/types";
import { formatMs, formatTime } from "../lib/format";
import { DecisionBadge, Empty } from "./ui";

function summaryOf(event: SafetyEvent): string {
  const violations = event.report.findings.filter((f) => f.severity === "violation");
  if (violations.length) {
    const first = violations[0]?.message ?? "";
    return violations.length > 1 ? `${first} (+${violations.length - 1} more)` : first;
  }
  const warnings = event.report.findings.length;
  return warnings ? `${warnings} near-limit warning${warnings > 1 ? "s" : ""}` : "No safety violations";
}

function injectedFaults(event: SafetyEvent): string[] {
  const faults = event.metadata?.injected_faults;
  return Array.isArray(faults) ? faults.map(String) : [];
}

export function DecisionFeed({
  events,
  selected,
  onSelect,
  limit = 60,
}: {
  events: SafetyEvent[];
  selected: number | null;
  onSelect: (sequence: number) => void;
  limit?: number;
}) {
  if (!events.length) return <Empty>Start a run to see DreamGuard's decisions.</Empty>;
  const newestFirst = events.slice(-limit).reverse();
  return (
    <ol className="max-h-96 space-y-1 overflow-y-auto pr-1" aria-label="Decision feed">
      {newestFirst.map((event) => {
        const faults = injectedFaults(event);
        const isSelected = event.sequence === selected;
        return (
          <li key={event.sequence}>
            <button
              type="button"
              onClick={() => onSelect(event.sequence)}
              aria-pressed={isSelected}
              className={`w-full rounded-lg px-3 py-2 text-left transition ${
                isSelected ? "bg-slate-700" : "bg-slate-800/50 hover:bg-slate-800"
              }`}
            >
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span className="font-mono">#{event.sequence}</span>
                <DecisionBadge decision={event.report.decision} />
                <span>risk {event.report.risk_score}</span>
                {faults.map((fault) => (
                  <span key={fault} className="rounded bg-violet-500/20 px-1.5 text-violet-200">
                    injected: {fault}
                  </span>
                ))}
                {event.halted && <span className="rounded bg-rose-600 px-1.5 text-white">halted</span>}
                <span className="ml-auto">
                  {formatTime(event.timestamp)} · {formatMs(event.report.latency_ms)}
                </span>
              </div>
              <p className="mt-1 truncate text-sm text-slate-200">{summaryOf(event)}</p>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
