import type { components } from "./schema";

type Schemas = components["schemas"];

export type RunStatus = Schemas["RunResponse"];
export type RunCreate = Schemas["RunCreate"];
export type RunSource = RunCreate["source"];
export type FaultResponse = Schemas["FaultResponse"];
export type Catalog = Schemas["CatalogResponse"];
export type SafetyReport = Schemas["SafetyReportResponse"];
export type Finding = Schemas["FindingResponse"];
export type SafetyEvent = Schemas["SafetyEventResponse"];
export type Profile = Schemas["ProfileResponse"];
export type MetricsSummary = Schemas["MetricsSummary"];
export type Metrics = Schemas["MetricsResponse"];
export type SessionSummary = Schemas["SessionSummaryResponse"];
export type SessionPage = Schemas["SessionEventsResponse"];

/** Messages pushed by the backend on /ws/events. */
export type StreamMessage =
  | { type: "run"; run: RunStatus }
  | { type: "event"; event: SafetyEvent };

export type Arm = "right" | "left";
export const ARMS: readonly Arm[] = ["right", "left"];
export const ACTION_KEYS: Record<Arm, "q_r_chunk" | "q_l_chunk"> = {
  right: "q_r_chunk",
  left: "q_l_chunk",
};

/** A chunk value as recorded: numbers, or "NaN" / "Infinity" strings for non-finite values. */
export type RecordedNumber = number | string;
