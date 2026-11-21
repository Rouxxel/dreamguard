import { useState } from "react";

import type { StreamState } from "../api/eventStream";
import { useCatalog, useMetrics, useProfile } from "../api/hooks";
import { CameraFeeds } from "../components/CameraFeeds";
import { DecisionFeed } from "../components/DecisionFeed";
import { EventDetail } from "../components/EventDetail";
import { FaultPanel } from "../components/FaultPanel";
import { JointLimitBars } from "../components/JointLimitBars";
import { MetricsCards } from "../components/MetricsCards";
import { RiskChart } from "../components/RiskChart";
import { RunControls } from "../components/RunControls";
import { Panel } from "../components/ui";

export function LivePage({ stream }: { stream: StreamState }) {
  const catalog = useCatalog();
  const profile = useProfile();
  const metrics = useMetrics(stream.run?.state === "running");
  const [selected, setSelected] = useState<number | null>(null);

  const latest = stream.events.at(-1);
  const selectedEvent = stream.events.find((e) => e.sequence === selected) ?? latest;
  const limits = profile.data?.config.joint_limits as Record<string, number[][]> | undefined;

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="space-y-4">
        <Panel title="Simulator cameras">
          <CameraFeeds cameras={catalog.data?.cameras} />
        </Panel>
        <Panel title="Run">
          <RunControls catalog={catalog.data} run={stream.run} />
        </Panel>
        <Panel title="Fault injection">
          <FaultPanel catalog={catalog.data} run={stream.run} />
        </Panel>
      </div>
      <div className="space-y-4">
        <Panel title="Safety metrics">
          <MetricsCards summary={metrics.data?.summary} />
        </Panel>
        <Panel title="Risk per action chunk">
          <RiskChart events={stream.events} onSelect={setSelected} />
        </Panel>
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel
            title="Decisions"
            actions={
              selected !== null && (
                <button
                  type="button"
                  className="text-xs text-sky-300 hover:underline"
                  onClick={() => setSelected(null)}
                >
                  Follow latest
                </button>
              )
            }
          >
            <DecisionFeed
              events={stream.events}
              selected={selectedEvent?.sequence ?? null}
              onSelect={setSelected}
            />
          </Panel>
          <Panel title="Why">
            <EventDetail event={selectedEvent} />
          </Panel>
        </div>
        <Panel title="Joint targets vs limits">
          <JointLimitBars
            event={selectedEvent}
            limits={limits}
            jointNames={catalog.data?.joint_names}
          />
        </Panel>
      </div>
    </div>
  );
}
