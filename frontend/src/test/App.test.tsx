import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import { CATALOG, JOINT_LIMIT_FINDING, LIMITS, makeEvent, makeRun } from "./fixtures";

class FakeSocket {
  static last: FakeSocket | null = null;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  readonly url: string;

  constructor(url: string) {
    this.url = url;
    FakeSocket.last = this;
  }

  close() {}

  emit(message: unknown) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }
}

const RESPONSES: Record<string, unknown> = {
  "/api/runs/catalog": CATALOG,
  "/api/runs/current": makeRun({ state: "idle", run_id: null, source: null }),
  "/api/safety/metrics": { run_id: null, summary: null },
  "/api/safety/profile": {
    name: "yam_sim",
    forward_kinematics: true,
    max_consecutive_blocks: 3,
    config: { joint_limits: LIMITS, action_hz: 20, require_workspace_check: true },
  },
  "/api/sessions": [],
};

beforeEach(() => {
  window.location.hash = "";
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      const key = path.split("?")[0] ?? path;
      return new Response(JSON.stringify(RESPONSES[key] ?? {}), { status: 200 });
    }),
  );
});

afterEach(() => vi.unstubAllGlobals());

function renderApp(client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

describe("App", () => {
  it("connects to the event stream and shows live decisions", async () => {
    renderApp();
    expect(FakeSocket.last?.url).toMatch(/\/ws\/events$/);
    act(() => FakeSocket.last?.onopen?.());
    expect(screen.getByRole("status")).toHaveTextContent("Live");

    act(() => {
      FakeSocket.last?.emit({ type: "run", run: makeRun() });
      FakeSocket.last?.emit({
        type: "event",
        event: makeEvent(1, { blocked: true, findings: [JOINT_LIMIT_FINDING], faults: ["joint_limit"] }),
      });
    });
    expect(await screen.findByText(/injected: joint_limit/)).toBeInTheDocument();
    expect(screen.getAllByText("BLOCK").length).toBeGreaterThan(0);
  });

  it("refetches metrics for every new decision, including the one that halts the run", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderApp(client);
    act(() => FakeSocket.last?.onopen?.());
    const metricCalls = () =>
      vi.mocked(fetch).mock.calls.filter(([path]) => String(path).startsWith("/api/safety/metrics")).length;
    await vi.waitFor(() => expect(client.getQueryData(["metrics"])).toBeDefined());
    expect(metricCalls()).toBe(1);

    act(() => {
      FakeSocket.last?.emit({ type: "run", run: makeRun({ state: "halted" }) });
      FakeSocket.last?.emit({ type: "event", event: makeEvent(1, { blocked: true, findings: [JOINT_LIMIT_FINDING] }) });
    });
    await vi.waitFor(() => expect(metricCalls()).toBe(2));
  });

  it("reports a disconnected live stream", () => {
    renderApp();
    act(() => FakeSocket.last?.onclose?.());
    expect(screen.getByRole("status")).toHaveTextContent("Live stream disconnected");
  });

  it("locks the paid Dream-1 source while paid calls are disabled", async () => {
    renderApp();
    const option = await screen.findByRole("option", { name: /Dream-1 \(live\) \(paid calls disabled\)/ });
    expect(option).toBeDisabled();
  });

  it("switches to the safety profile page", async () => {
    renderApp();
    await userEvent.click(screen.getByRole("button", { name: "Safety profile" }));
    expect(await screen.findByText("Profile: yam_sim")).toBeInTheDocument();
    expect(window.location.hash).toBe("#profile");
  });
});
