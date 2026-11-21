import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { DecisionFeed } from "../components/DecisionFeed";
import { EventDetail } from "../components/EventDetail";
import { FaultPanel } from "../components/FaultPanel";
import { JointLimitBars } from "../components/JointLimitBars";
import { MetricsCards } from "../components/MetricsCards";
import { CATALOG, JOINT_LIMIT_FINDING, LIMITS, makeEvent, makeRun } from "./fixtures";

function withQuery(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("DecisionFeed", () => {
  const events = [
    makeEvent(1),
    makeEvent(2, { blocked: true, findings: [JOINT_LIMIT_FINDING], faults: ["joint_limit"] }),
  ];

  it("lists the newest decision first with its reason and injected fault", () => {
    render(<DecisionFeed events={events} selected={null} onSelect={() => {}} />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("#2");
    expect(items[0]).toHaveTextContent("BLOCK");
    expect(items[0]).toHaveTextContent("injected: joint_limit");
    expect(items[0]).toHaveTextContent("outside [-1.571, 1.571]");
    expect(items[1]).toHaveTextContent("No safety violations");
  });

  it("selects a decision on click", async () => {
    const onSelect = vi.fn();
    render(<DecisionFeed events={events} selected={null} onSelect={onSelect} />);
    await userEvent.click(screen.getAllByRole("button")[1]!);
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("explains the empty state", () => {
    render(<DecisionFeed events={[]} selected={null} onSelect={() => {}} />);
    expect(screen.getByText(/Start a run/)).toBeInTheDocument();
  });
});

describe("EventDetail", () => {
  it("shows that a blocked action never reached the robot, with its findings", () => {
    const event = makeEvent(7, { blocked: true, findings: [JOINT_LIMIT_FINDING], faults: ["joint_limit"] });
    render(<EventDetail event={event} />);
    expect(screen.getByText(/never reached the controller/)).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Findings" })).toHaveTextContent("joint_limit");
    expect(screen.getByText("joint_limit", { selector: "dd" })).toBeInTheDocument();
  });
});

describe("MetricsCards", () => {
  it("renders the PRD metrics", () => {
    render(
      <MetricsCards
        summary={{
          actions_evaluated: 12,
          approved: 10,
          blocked: 2,
          executed: 10,
          halts: 0,
          unsafe_injected: 2,
          unsafe_prevented: 2,
          unsafe_missed: 0,
          false_rejections: 0,
          warnings: 0,
          violations_by_check: { joint_limit: 3 },
          latency_ms: { p50: 1.5, p95: 4.25, max: 5 },
          sources: ["fake"],
          first_timestamp: null,
          last_timestamp: null,
        }}
      />,
    );
    expect(screen.getByText("Actions evaluated").nextSibling).toHaveTextContent("12");
    expect(screen.getByText("Unsafe prevented").nextSibling).toHaveTextContent("2 / 2");
    expect(screen.getByText("Latency p95").nextSibling).toHaveTextContent("4.25 ms");
  });
});

describe("FaultPanel", () => {
  it("enables faults only for a running scripted run", () => {
    const { rerender } = render(withQuery(<FaultPanel catalog={CATALOG} run={makeRun()} />));
    expect(screen.getByRole("button", { name: /Joint limit/ })).toBeEnabled();

    rerender(withQuery(<FaultPanel catalog={CATALOG} run={makeRun({ source: "replay" })} />));
    expect(screen.getByRole("button", { name: /Joint limit/ })).toBeDisabled();

    rerender(withQuery(<FaultPanel catalog={CATALOG} run={makeRun({ state: "completed" })} />));
    expect(screen.getByRole("button", { name: /Joint limit/ })).toBeDisabled();
  });

  it("posts the fault for the current run", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ run_id: "run-1", fault: "nan", description: "NaN target" }), {
        status: 202,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(withQuery(<FaultPanel catalog={CATALOG} run={makeRun()} />));
    await userEvent.click(screen.getByRole("button", { name: /NaN value/ }));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/runs/run-1/faults",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ fault: "nan" }) }),
    );
    vi.unstubAllGlobals();
  });
});

describe("JointLimitBars", () => {
  it("marks joints whose targets leave the limits", () => {
    const event = makeEvent(1, { rows: [[0, 1.047, 1.047, 1.7, 0, 0, 0.5]] });
    render(<JointLimitBars event={event} limits={LIMITS} jointNames={CATALOG.joint_names} />);
    expect(screen.getByTestId("right-joint-3")).toHaveTextContent("outside limits");
    expect(screen.getByTestId("right-joint-0")).not.toHaveTextContent("outside limits");
  });
});
