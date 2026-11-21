import { describe, expect, it } from "vitest";

import {
  MAX_EVENTS,
  initialStreamState,
  parseStreamMessage,
  streamReducer,
  type StreamState,
} from "../api/eventStream";
import { toNumber } from "../lib/format";
import { jointRanges, percentOf } from "../lib/joints";
import { HOME, LIMITS, makeEvent, makeRun } from "./fixtures";

const withRun = (runId = "run-1"): StreamState =>
  streamReducer(initialStreamState, { type: "message", message: { type: "run", run: makeRun({ run_id: runId }) } });

describe("streamReducer", () => {
  it("tracks the connection state", () => {
    const state = streamReducer(initialStreamState, { type: "connection", connection: "open" });
    expect(state.connection).toBe("open");
  });

  it("appends events of the current run in order", () => {
    let state = withRun();
    state = streamReducer(state, { type: "message", message: { type: "event", event: makeEvent(1) } });
    state = streamReducer(state, { type: "message", message: { type: "event", event: makeEvent(2) } });
    expect(state.events.map((e) => e.sequence)).toEqual([1, 2]);
  });

  it("ignores duplicate and foreign events", () => {
    let state = withRun();
    const event = { type: "message", message: { type: "event", event: makeEvent(1) } } as const;
    state = streamReducer(streamReducer(state, event), event);
    state = streamReducer(state, {
      type: "message",
      message: { type: "event", event: makeEvent(9, { sessionId: "old-run" }) },
    });
    expect(state.events.map((e) => e.sequence)).toEqual([1]);
  });

  it("clears events when a new run starts but keeps them on status updates", () => {
    let state = withRun();
    state = streamReducer(state, { type: "message", message: { type: "event", event: makeEvent(1) } });
    state = streamReducer(state, {
      type: "message",
      message: { type: "run", run: makeRun({ state: "halted" }) },
    });
    expect(state.events).toHaveLength(1);
    state = streamReducer(state, { type: "message", message: { type: "run", run: makeRun({ run_id: "run-2" }) } });
    expect(state.events).toHaveLength(0);
  });

  it("keeps at most MAX_EVENTS events", () => {
    let state = withRun();
    for (let i = 1; i <= MAX_EVENTS + 5; i += 1) {
      state = streamReducer(state, { type: "message", message: { type: "event", event: makeEvent(i) } });
    }
    expect(state.events).toHaveLength(MAX_EVENTS);
    expect(state.events[0]?.sequence).toBe(6);
  });
});

describe("parseStreamMessage", () => {
  it("accepts run and event messages", () => {
    expect(parseStreamMessage(JSON.stringify({ type: "run", run: makeRun() }))?.type).toBe("run");
    expect(parseStreamMessage(JSON.stringify({ type: "event", event: makeEvent(1) }))?.type).toBe("event");
  });

  it("rejects malformed messages", () => {
    expect(parseStreamMessage("not json")).toBeNull();
    expect(parseStreamMessage(JSON.stringify({ type: "other" }))).toBeNull();
    expect(parseStreamMessage(42)).toBeNull();
  });
});

describe("jointRanges", () => {
  it("reports limits, measured position and target range", () => {
    const event = makeEvent(1, { rows: [[...HOME, 0.5], [0.2, 1.1, 1.0, 0, 0, 0, 0.5]] });
    const [base] = jointRanges(event, "right", LIMITS);
    expect(base).toMatchObject({ joint: 0, low: -2.618, high: 3.054, current: 0, min: 0, max: 0.2 });
    expect(base?.violated).toBe(false);
  });

  it("flags targets outside limits and non-finite targets", () => {
    const outside = makeEvent(1, { rows: [[0, 1.047, 1.047, 1.7, 0, 0, 0.5]] });
    expect(jointRanges(outside, "right", LIMITS)[3]?.violated).toBe(true);
    const nan = makeEvent(1, { rows: [["NaN", 1.047, 1.047, 0, 0, 0, 0.5]] });
    expect(jointRanges(nan, "right", LIMITS)[0]).toMatchObject({ violated: true, min: null });
  });

  it("handles a missing arm chunk", () => {
    const event = makeEvent(1);
    delete (event.action as Record<string, unknown>).q_l_chunk;
    expect(jointRanges(event, "left", LIMITS)[0]).toMatchObject({ min: null, max: null, violated: false });
  });
});

describe("helpers", () => {
  it("clamps percentages", () => {
    expect(percentOf(5, 0, 10)).toBe(50);
    expect(percentOf(-1, 0, 10)).toBe(0);
    expect(percentOf(11, 0, 10)).toBe(100);
  });

  it("decodes recorded non-finite values", () => {
    expect(toNumber("Infinity")).toBe(Infinity);
    expect(toNumber("-Infinity")).toBe(-Infinity);
    expect(Number.isNaN(toNumber("NaN"))).toBe(true);
    expect(toNumber(1.5)).toBe(1.5);
  });
});
