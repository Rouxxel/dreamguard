import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { SafetyEvent } from "../api/types";
import { riskColor } from "../lib/format";
import { Empty } from "./ui";

export const RISK_CHART_POINTS = 120;

export function RiskChart({
  events,
  onSelect,
}: {
  events: SafetyEvent[];
  onSelect?: (sequence: number) => void;
}) {
  if (!events.length) return <Empty>No decisions yet.</Empty>;
  const data = events.slice(-RISK_CHART_POINTS).map((e) => ({
    sequence: e.sequence,
    risk: e.report.risk_score,
    decision: e.report.decision,
  }));
  return (
    <div className="h-48" aria-label="Risk score per action chunk">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 4, right: 8, bottom: 0, left: -20 }}
          onClick={(state) => {
            const sequence = data[Number(state?.activeTooltipIndex)]?.sequence;
            if (sequence !== undefined) onSelect?.(sequence);
          }}
        >
          <CartesianGrid stroke="#1e293b" vertical={false} />
          <XAxis dataKey="sequence" stroke="#64748b" fontSize={11} />
          <YAxis domain={[0, 100]} stroke="#64748b" fontSize={11} />
          <Tooltip
            cursor={{ fill: "#1e293b" }}
            contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
            formatter={(value, _name, item) => [`${String(value)} (${item.payload.decision})`, "Risk"]}
            labelFormatter={(label) => `Chunk #${String(label)}`}
          />
          <Bar dataKey="risk" isAnimationActive={false} minPointSize={2}>
            {data.map((point) => (
              <Cell key={point.sequence} fill={riskColor(point.risk)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
