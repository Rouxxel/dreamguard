import type {
  Catalog,
  FaultResponse,
  Metrics,
  Profile,
  RunCreate,
  RunStatus,
  SessionPage,
  SessionSummary,
} from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function detailMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((d) => (d as { msg?: string }).msg ?? JSON.stringify(d)).join("; ");
    }
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(response.status, detailMessage(body, response.statusText));
  }
  return body as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  catalog: () => request<Catalog>("/api/runs/catalog"),
  currentRun: () => request<RunStatus>("/api/runs/current"),
  startRun: (body: RunCreate) => post<RunStatus>("/api/runs", body),
  stopRun: (runId: string) => post<RunStatus>(`/api/runs/${encodeURIComponent(runId)}/stop`),
  resetRun: (runId: string) => post<RunStatus>(`/api/runs/${encodeURIComponent(runId)}/reset`),
  injectFault: (runId: string, fault: string) =>
    post<FaultResponse>(`/api/runs/${encodeURIComponent(runId)}/faults`, { fault }),
  metrics: () => request<Metrics>("/api/safety/metrics"),
  profile: () => request<Profile>("/api/safety/profile"),
  sessions: () => request<SessionSummary[]>("/api/sessions"),
  session: (sessionId: string, offset = 0, limit = 1000) =>
    request<SessionPage>(
      `/api/sessions/${encodeURIComponent(sessionId)}?offset=${offset}&limit=${limit}`,
    ),
};

export const cameraUrl = (camera: string) => `/api/stream/camera/${encodeURIComponent(camera)}`;

export function eventsSocketUrl(location: Location = window.location): string {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${location.host}/ws/events`;
}
