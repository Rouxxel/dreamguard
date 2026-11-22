import { ACTION_KEYS, type Arm, type SafetyEvent } from "../api/types";
import { toNumber } from "./format";

export const JOINTS_PER_ARM = 6;

export interface JointRange {
  joint: number;
  low: number;
  high: number;
  /** Measured joint position before the chunk (null when unknown). */
  current: number | null;
  /** Lowest / highest target of the chunk (null when the chunk has no valid targets). */
  min: number | null;
  max: number | null;
  /** True when a target is outside the limits or not a finite number. */
  violated: boolean;
}

type Limits = Record<string, number[][]>;

function rowsOf(event: SafetyEvent, arm: Arm): unknown[][] {
  const chunk = event.action?.[ACTION_KEYS[arm]];
  return Array.isArray(chunk) ? chunk.filter(Array.isArray) : [];
}

function currentOf(event: SafetyEvent, arm: Arm, joint: number): number | null {
  const joints = event.current_joints?.[arm];
  if (!Array.isArray(joints)) return null;
  const value = toNumber(joints[joint]);
  return Number.isFinite(value) ? value : null;
}

/** Per-joint limits, measured position and chunk target range for one arm of one event. */
export function jointRanges(event: SafetyEvent, arm: Arm, limits: Limits): JointRange[] {
  const rows = rowsOf(event, arm);
  const armLimits = limits[arm] ?? [];
  return Array.from({ length: JOINTS_PER_ARM }, (_, joint) => {
    const [low = -Math.PI, high = Math.PI] = armLimits[joint] ?? [];
    const targets = rows.map((row) => toNumber(row[joint]));
    const finite = targets.filter(Number.isFinite);
    const min = finite.length ? Math.min(...finite) : null;
    const max = finite.length ? Math.max(...finite) : null;
    const violated =
      finite.length !== targets.length ||
      (min !== null && min < low) ||
      (max !== null && max > high);
    return { joint, low, high, current: currentOf(event, arm, joint), min, max, violated };
  });
}

/** Position of ``value`` within [low, high] as a clamped percentage. */
export function percentOf(value: number, low: number, high: number): number {
  if (high <= low) return 0;
  return Math.max(0, Math.min(100, ((value - low) / (high - low)) * 100));
}
