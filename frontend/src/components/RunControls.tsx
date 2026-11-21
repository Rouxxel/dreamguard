import { useState } from "react";

import { useResetRun, useSessions, useStartRun, useStopRun } from "../api/hooks";
import type { Catalog, RunSource, RunStatus } from "../api/types";
import { RUN_STATE_STYLES } from "../lib/format";
import { Button, ErrorNote } from "./ui";

const ACTIVE = new Set(["running", "halted"]);

export function RunControls({ catalog, run }: { catalog: Catalog | undefined; run: RunStatus | null }) {
  const [source, setSource] = useState<RunSource>("fake");
  const [prompt, setPrompt] = useState("tidy up the table");
  const [replayId, setReplayId] = useState("");
  const sessions = useSessions();
  const start = useStartRun();
  const stop = useStopRun();
  const reset = useResetRun();

  const active = run !== null && ACTIVE.has(run.state);
  const sources = Object.entries(catalog?.sources ?? {}) as [RunSource, Catalog["sources"][string]][];
  const paidLocked = (s: RunSource) => Boolean(catalog?.sources[s]?.paid) && !catalog?.paid_calls_allowed;
  const canStart = !active && !paidLocked(source) && (source !== "replay" || replayId !== "");

  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${RUN_STATE_STYLES[run?.state ?? "idle"]}`}>
          {run?.state ?? "idle"}
        </span>
        {run?.run_id && <span className="font-mono text-xs text-slate-400">{run.run_id}</span>}
        {run && run.run_id && (
          <span className="text-xs text-slate-400">
            {run.chunks} chunks · {run.rows_played} rows executed
            {run.source === "dream1" && ` · ${run.paid_calls} paid calls`}
          </span>
        )}
      </div>

      <fieldset className="grid gap-2 sm:grid-cols-2" disabled={active}>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-slate-400">Action source</span>
          <select
            aria-label="Action source"
            className="rounded-md bg-slate-800 px-2 py-1.5"
            value={source}
            onChange={(e) => setSource(e.target.value as RunSource)}
          >
            {sources.map(([id, info]) => (
              <option key={id} value={id} disabled={paidLocked(id)}>
                {info.label}
                {paidLocked(id) ? " (paid calls disabled)" : ""}
              </option>
            ))}
          </select>
        </label>
        {source === "replay" ? (
          <label className="flex flex-col gap-1">
            <span className="text-xs text-slate-400">Session to replay</span>
            <select
              aria-label="Session to replay"
              className="rounded-md bg-slate-800 px-2 py-1.5"
              value={replayId}
              onChange={(e) => setReplayId(e.target.value)}
            >
              <option value="">Select a recorded session</option>
              {(sessions.data ?? []).map((s) => (
                <option key={s.session_id} value={s.session_id}>
                  {s.session_id} ({s.summary.actions_evaluated} actions)
                </option>
              ))}
            </select>
          </label>
        ) : (
          <label className="flex flex-col gap-1">
            <span className="text-xs text-slate-400">Prompt</span>
            <input
              aria-label="Prompt"
              className="rounded-md bg-slate-800 px-2 py-1.5"
              value={prompt}
              maxLength={500}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </label>
        )}
      </fieldset>

      <div className="flex flex-wrap gap-2">
        <Button
          disabled={!canStart || start.isPending}
          onClick={() =>
            start.mutate({
              source,
              prompt: source === "replay" ? "" : prompt,
              replay_session_id: source === "replay" ? replayId : null,
            })
          }
        >
          Start run
        </Button>
        <Button
          variant="ghost"
          disabled={!active || !run?.run_id || stop.isPending}
          onClick={() => run?.run_id && stop.mutate(run.run_id)}
        >
          Stop
        </Button>
        {run?.state === "halted" && (
          <Button variant="danger" disabled={reset.isPending} onClick={() => run.run_id && reset.mutate(run.run_id)}>
            Reviewed – resume run
          </Button>
        )}
      </div>
      {run?.state === "halted" && (
        <p className="rounded-md bg-rose-950/60 px-3 py-2 text-rose-200">
          The run halted after {run.consecutive_blocks} blocked actions in a row. Review the
          findings before resuming.
        </p>
      )}
      {run?.error && <ErrorNote error={run.error} />}
      <ErrorNote error={start.error ?? stop.error ?? reset.error} />
    </div>
  );
}
