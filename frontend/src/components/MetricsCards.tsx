import type { MetricsSummary } from "../api/types";
import { formatMs } from "../lib/format";

interface Card {
  label: string;
  value: string | number;
  tone?: "good" | "bad" | "neutral";
  hint?: string;
}

const TONES = {
  good: "text-emerald-300",
  bad: "text-rose-300",
  neutral: "text-slate-100",
};

export function MetricsCards({ summary }: { summary: MetricsSummary | undefined }) {
  if (!summary) return null;
  const cards: Card[] = [
    { label: "Actions evaluated", value: summary.actions_evaluated },
    { label: "Approved", value: summary.approved, tone: "good" },
    { label: "Blocked", value: summary.blocked, tone: summary.blocked ? "bad" : "neutral" },
    {
      label: "Unsafe prevented",
      value: `${summary.unsafe_prevented} / ${summary.unsafe_injected}`,
      tone: "good",
      hint: "Injected unsafe chunks that never reached the robot",
    },
    {
      label: "Unsafe missed",
      value: summary.unsafe_missed,
      tone: summary.unsafe_missed ? "bad" : "good",
      hint: "Injected unsafe chunks that were executed",
    },
    {
      label: "False rejections",
      value: summary.false_rejections,
      tone: summary.false_rejections ? "bad" : "good",
      hint: "Scripted chunks without an injected fault that were blocked",
    },
    { label: "Latency p50", value: formatMs(summary.latency_ms.p50) },
    { label: "Latency p95", value: formatMs(summary.latency_ms.p95) },
  ];
  return (
    <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {cards.map((card) => (
        <div key={card.label} className="rounded-lg bg-slate-800/60 p-3" title={card.hint}>
          <dt className="text-xs text-slate-400">{card.label}</dt>
          <dd className={`mt-1 text-xl font-semibold tabular-nums ${TONES[card.tone ?? "neutral"]}`}>
            {card.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
