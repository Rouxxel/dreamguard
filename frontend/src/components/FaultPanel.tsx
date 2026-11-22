import { useInjectFault } from "../api/hooks";
import type { Catalog, RunStatus } from "../api/types";
import { ErrorNote } from "./ui";

export function FaultPanel({ catalog, run }: { catalog: Catalog | undefined; run: RunStatus | null }) {
  const inject = useInjectFault();
  const enabled = run?.state === "running" && run.source === "fake" && Boolean(run.run_id);
  const faults = Object.entries(catalog?.faults ?? {});
  return (
    <div>
      <p className="mb-2 text-xs text-slate-400">
        {enabled
          ? "Each click makes one upcoming scripted chunk unsafe. DreamGuard must block it before the robot moves; three in a row halt the run."
          : "Start a scripted (offline) run to inject faults."}
      </p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {faults.map(([id, fault]) => (
          <button
            key={id}
            type="button"
            disabled={!enabled || inject.isPending}
            title={fault.description}
            onClick={() => run?.run_id && inject.mutate({ runId: run.run_id, fault: id })}
            className="rounded-lg border border-violet-500/30 bg-violet-500/10 px-2 py-1.5 text-left text-xs text-violet-100 transition hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <span className="block font-semibold">{fault.label}</span>
            <span className="text-[10px] text-violet-300/80">expects {fault.expected_check}</span>
          </button>
        ))}
      </div>
      <ErrorNote error={inject.error} />
    </div>
  );
}
