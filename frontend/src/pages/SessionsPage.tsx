import { useState } from "react";

import { useCatalog, useProfile, useSession, useSessions, useStartRun } from "../api/hooks";
import { EventDetail } from "../components/EventDetail";
import { JointLimitBars } from "../components/JointLimitBars";
import { MetricsCards } from "../components/MetricsCards";
import { RiskChart } from "../components/RiskChart";
import { Button, Empty, ErrorNote, Panel } from "../components/ui";
import { formatDateTime } from "../lib/format";

function SessionReplay({ sessionId, onReplayed }: { sessionId: string; onReplayed: () => void }) {
  const session = useSession(sessionId);
  const profile = useProfile();
  const catalog = useCatalog();
  const startRun = useStartRun();
  const [index, setIndex] = useState(0);

  if (session.isLoading) return <Empty>Loading session…</Empty>;
  if (session.error) return <ErrorNote error={session.error} />;
  const events = session.data?.events ?? [];
  if (!events.length) return <Empty>This session has no events.</Empty>;

  const position = Math.min(index, events.length - 1);
  const event = events[position];
  const limits = profile.data?.config.joint_limits as Record<string, number[][]> | undefined;
  const truncated = (session.data?.total ?? 0) > events.length;

  return (
    <div className="space-y-4">
      <Panel
        title="Session metrics"
        actions={
          <Button
            variant="ghost"
            disabled={startRun.isPending}
            onClick={() =>
              startRun.mutate(
                { source: "replay", prompt: "", replay_session_id: sessionId },
                { onSuccess: onReplayed },
              )
            }
          >
            Replay through the guard
          </Button>
        }
      >
        <MetricsCards summary={session.data?.summary} />
        <ErrorNote error={startRun.error} />
      </Panel>
      <Panel title="Risk per action chunk">
        <RiskChart
          events={events}
          onSelect={(sequence) => setIndex(Math.max(0, events.findIndex((e) => e.sequence === sequence)))}
        />
      </Panel>
      <Panel title="Step through decisions">
        <div className="mb-3 flex items-center gap-2 text-sm">
          <Button variant="ghost" disabled={position === 0} onClick={() => setIndex(position - 1)}>
            ← Previous
          </Button>
          <input
            type="range"
            aria-label="Decision position"
            min={0}
            max={events.length - 1}
            value={position}
            onChange={(e) => setIndex(Number(e.target.value))}
            className="flex-1"
          />
          <Button
            variant="ghost"
            disabled={position === events.length - 1}
            onClick={() => setIndex(position + 1)}
          >
            Next →
          </Button>
          <span className="w-20 text-right font-mono text-xs text-slate-400">
            {position + 1} / {events.length}
          </span>
        </div>
        {truncated && (
          <p className="mb-2 text-xs text-amber-300">
            Showing the first {events.length} of {session.data?.total} decisions.
          </p>
        )}
        <div className="grid gap-4 lg:grid-cols-2">
          <EventDetail event={event} />
          <JointLimitBars event={event} limits={limits} jointNames={catalog.data?.joint_names} />
        </div>
      </Panel>
    </div>
  );
}

export function SessionsPage({ onReplayStarted }: { onReplayStarted: () => void }) {
  const sessions = useSessions();
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,4fr)_minmax(0,8fr)]">
      <Panel title="Recorded sessions">
        {sessions.error && <ErrorNote error={sessions.error} />}
        {sessions.data?.length === 0 && <Empty>No sessions recorded yet.</Empty>}
        <ul className="max-h-[70vh] space-y-1 overflow-y-auto" aria-label="Recorded sessions">
          {(sessions.data ?? []).map(({ session_id, summary }) => (
            <li key={session_id}>
              <button
                type="button"
                aria-pressed={session_id === selected}
                onClick={() => setSelected(session_id)}
                className={`w-full rounded-lg px-3 py-2 text-left text-sm transition ${
                  session_id === selected ? "bg-slate-700" : "bg-slate-800/50 hover:bg-slate-800"
                }`}
              >
                <div className="font-mono text-xs text-slate-300">{session_id}</div>
                <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-slate-400">
                  <span>{formatDateTime(summary.first_timestamp)}</span>
                  <span>{summary.sources.join(", ") || "–"}</span>
                  <span>{summary.actions_evaluated} actions</span>
                  <span className={summary.blocked ? "text-rose-300" : undefined}>
                    {summary.blocked} blocked
                  </span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      </Panel>
      <div>
        {selected ? (
          <SessionReplay key={selected} sessionId={selected} onReplayed={onReplayStarted} />
        ) : (
          <Panel title="Replay">
            <Empty>Select a session to step through its decisions.</Empty>
          </Panel>
        )}
      </div>
    </div>
  );
}
