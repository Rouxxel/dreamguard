import { ARMS, type SafetyEvent } from "../api/types";
import { jointRanges, percentOf } from "../lib/joints";
import { Empty } from "./ui";

export function JointLimitBars({
  event,
  limits,
  jointNames,
}: {
  event: SafetyEvent | undefined;
  limits: Record<string, number[][]> | undefined;
  jointNames?: string[];
}) {
  if (!event || !limits) return <Empty>Joint targets appear with the first decision.</Empty>;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {ARMS.map((arm) => (
        <div key={arm}>
          <h3 className="mb-2 text-xs font-semibold uppercase text-slate-400">{arm} arm</h3>
          <ul className="space-y-2">
            {jointRanges(event, arm, limits).map((range) => {
              const name = jointNames?.[range.joint] ?? `joint${range.joint + 1}`;
              const hasTargets = range.min !== null && range.max !== null;
              const from = hasTargets ? percentOf(range.min ?? 0, range.low, range.high) : 0;
              const to = hasTargets ? percentOf(range.max ?? 0, range.low, range.high) : 0;
              return (
                <li key={range.joint} data-testid={`${arm}-joint-${range.joint}`}>
                  <div className="flex justify-between text-[11px] text-slate-400">
                    <span className={range.violated ? "font-semibold text-rose-300" : undefined}>
                      {name}
                      {range.violated && " · outside limits"}
                    </span>
                    <span className="font-mono">
                      [{range.low.toFixed(2)}, {range.high.toFixed(2)}] rad
                    </span>
                  </div>
                  <div className="relative mt-1 h-2.5 rounded-full bg-slate-800">
                    {hasTargets && (
                      <div
                        className={`absolute inset-y-0 rounded-full ${range.violated ? "bg-rose-500" : "bg-sky-500"}`}
                        style={{ left: `${from}%`, width: `${Math.max(to - from, 1)}%` }}
                        title={`Targets ${range.min?.toFixed(3)} … ${range.max?.toFixed(3)} rad`}
                      />
                    )}
                    {range.current !== null && (
                      <div
                        className="absolute -top-0.5 h-3.5 w-0.5 bg-white"
                        style={{ left: `${percentOf(range.current, range.low, range.high)}%` }}
                        title={`Measured ${range.current.toFixed(3)} rad`}
                      />
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      <p className="text-[11px] text-slate-500 sm:col-span-2">
        Bar: range of the chunk's joint targets within the joint limits. White mark: measured
        position before the chunk.
      </p>
    </div>
  );
}
