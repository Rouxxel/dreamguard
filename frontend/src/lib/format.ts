import type { SafetyReport } from "../api/types";

export type Decision = SafetyReport["decision"];

export const DECISION_STYLES: Record<Decision, string> = {
  APPROVE: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/40",
  MODIFY: "bg-amber-500/15 text-amber-300 ring-amber-500/40",
  BLOCK: "bg-rose-500/15 text-rose-300 ring-rose-500/40",
};

export const RUN_STATE_STYLES: Record<string, string> = {
  idle: "bg-slate-700 text-slate-200",
  running: "bg-emerald-600 text-white",
  halted: "bg-rose-600 text-white",
  stopped: "bg-slate-600 text-white",
  completed: "bg-sky-700 text-white",
  error: "bg-rose-800 text-white",
};

export function riskColor(risk: number): string {
  if (risk >= 70) return "#fb7185";
  if (risk > 0) return "#fbbf24";
  return "#34d399";
}

export function formatMs(value: number | null | undefined): string {
  return value === null || value === undefined ? "–" : `${value.toFixed(2)} ms`;
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleTimeString();
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

/** Recorded values may be numbers or "NaN" / "Infinity" / "-Infinity" strings. */
export function toNumber(value: unknown): number {
  if (typeof value === "number") return value;
  if (value === "Infinity") return Infinity;
  if (value === "-Infinity") return -Infinity;
  return NaN;
}
