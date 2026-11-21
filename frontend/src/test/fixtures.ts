import type { Catalog, Finding, RunStatus, SafetyEvent } from "../api/types";

export const HOME = [0, 1.047, 1.047, 0, 0, 0];

export const LIMITS: Record<string, number[][]> = {
  right: [[-2.618, 3.054], [0, 3.665], [0, 3.665], [-1.571, 1.571], [-1.571, 1.571], [-2.094, 2.094]],
  left: [[-2.618, 3.054], [0, 3.665], [0, 3.665], [-1.571, 1.571], [-1.571, 1.571], [-2.094, 2.094]],
};

export function makeRun(overrides: Partial<RunStatus> = {}): RunStatus {
  return {
    run_id: "run-1",
    state: "running",
    source: "fake",
    prompt: "",
    chunks: 0,
    rows_played: 0,
    consecutive_blocks: 0,
    paid_calls: 0,
    started_at: null,
    finished_at: null,
    error: null,
    replay_session_id: null,
    ...overrides,
  };
}

export function makeEvent(
  sequence: number,
  {
    blocked = false,
    findings = [] as Finding[],
    faults = [] as string[],
    sessionId = "run-1",
    rows = [[...HOME, 0.5]] as unknown[][],
  } = {},
): SafetyEvent {
  return {
    session_id: sessionId,
    sequence,
    timestamp: "2026-11-21T19:00:00+00:00",
    source: "fake",
    executed: !blocked,
    halted: false,
    error: null,
    metadata: faults.length ? { injected_faults: faults } : {},
    report: {
      decision: blocked ? "BLOCK" : "APPROVE",
      approved: !blocked,
      risk_score: blocked ? 90 : 0,
      findings,
      checked_rows: rows.length,
      latency_ms: 1.25,
    },
    action: { q_r_chunk: rows, q_l_chunk: [[...HOME, 0.5]] },
    current_joints: { right: HOME, left: HOME },
  };
}

export const JOINT_LIMIT_FINDING: Finding = {
  check: "joint_limit",
  severity: "violation",
  message: "right row 3: joint 3 target 1.700 outside [-1.571, 1.571] rad",
  arm: "right",
  row: 3,
  joint: 3,
  value: 1.7,
  limit: 1.571,
};

export const CATALOG: Catalog = {
  sources: {
    fake: { label: "Scripted (offline)", description: "", paid: false },
    replay: { label: "Replay session", description: "", paid: false },
    dream1: { label: "Dream-1 (live)", description: "", paid: true },
  },
  faults: {
    joint_limit: { label: "Joint limit", description: "ramps past limit", expected_check: "joint_limit" },
    nan: { label: "NaN value", description: "NaN target", expected_check: "action_format" },
  },
  cameras: { overhead: "Overhead", wrist_l: "Left wrist", wrist_r: "Right wrist" },
  joint_names: ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"],
  paid_calls_allowed: false,
};
