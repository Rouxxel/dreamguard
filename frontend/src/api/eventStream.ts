import { useEffect, useReducer } from "react";

import { eventsSocketUrl } from "./client";
import type { RunStatus, SafetyEvent, StreamMessage } from "./types";

export const MAX_EVENTS = 500;

export type ConnectionState = "connecting" | "open" | "closed";

export interface StreamState {
  connection: ConnectionState;
  run: RunStatus | null;
  /** Events of the current run, newest last (bounded to MAX_EVENTS). */
  events: SafetyEvent[];
}

export type StreamAction =
  | { type: "connection"; connection: ConnectionState }
  | { type: "message"; message: StreamMessage };

export const initialStreamState: StreamState = { connection: "connecting", run: null, events: [] };

export function streamReducer(state: StreamState, action: StreamAction): StreamState {
  if (action.type === "connection") {
    return { ...state, connection: action.connection };
  }
  const { message } = action;
  if (message.type === "run") {
    const newRun = message.run.run_id !== state.run?.run_id;
    return { ...state, run: message.run, events: newRun ? [] : state.events };
  }
  const event = message.event;
  if (state.run && event.session_id !== state.run.run_id) {
    return state; // a late event from a previous run
  }
  if (state.events.some((e) => e.sequence === event.sequence)) {
    return state;
  }
  const events = [...state.events, event].slice(-MAX_EVENTS);
  return { ...state, events };
}

export function parseStreamMessage(data: unknown): StreamMessage | null {
  if (typeof data !== "string") return null;
  try {
    const parsed = JSON.parse(data) as Partial<StreamMessage>;
    if (parsed.type === "run" && "run" in parsed) return parsed as StreamMessage;
    if (parsed.type === "event" && "event" in parsed) return parsed as StreamMessage;
  } catch {
    // ignore malformed messages
  }
  return null;
}

/** Live run status and safety events from /ws/events, reconnecting with backoff. */
export function useEventStream(url: string = eventsSocketUrl()): StreamState {
  const [state, dispatch] = useReducer(streamReducer, initialStreamState);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let disposed = false;

    const connect = () => {
      dispatch({ type: "connection", connection: "connecting" });
      socket = new WebSocket(url);
      socket.onopen = () => {
        attempt = 0;
        dispatch({ type: "connection", connection: "open" });
      };
      socket.onmessage = (event: MessageEvent) => {
        const message = parseStreamMessage(event.data);
        if (message) dispatch({ type: "message", message });
      };
      socket.onclose = () => {
        if (disposed) return;
        dispatch({ type: "connection", connection: "closed" });
        attempt += 1;
        retryTimer = setTimeout(connect, Math.min(10000, 500 * 2 ** attempt));
      };
    };

    connect();
    return () => {
      disposed = true;
      clearTimeout(retryTimer);
      socket?.close();
    };
  }, [url]);

  return state;
}
