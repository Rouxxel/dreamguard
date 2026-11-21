import { useEffect, useState } from "react";

import { type ConnectionState, useEventStream } from "./api/eventStream";
import { LivePage } from "./pages/LivePage";
import { ProfilePage } from "./pages/ProfilePage";
import { SessionsPage } from "./pages/SessionsPage";

const TABS = { live: "Live", sessions: "Sessions", profile: "Safety profile" } as const;
type Tab = keyof typeof TABS;

function tabFromHash(): Tab {
  const hash = window.location.hash.replace("#", "");
  return hash in TABS ? (hash as Tab) : "live";
}

const CONNECTION: Record<ConnectionState, { label: string; dot: string }> = {
  open: { label: "Live", dot: "bg-emerald-400" },
  connecting: { label: "Connecting…", dot: "bg-amber-400" },
  closed: { label: "Live stream disconnected", dot: "bg-rose-500" },
};

export default function App() {
  const stream = useEventStream();
  const [tab, setTab] = useState<Tab>(tabFromHash);

  useEffect(() => {
    const onHashChange = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    if (window.location.hash !== `#${tab}`) window.history.replaceState(null, "", `#${tab}`);
  }, [tab]);

  const select = (next: Tab) => setTab(next);
  const connection = CONNECTION[stream.connection];

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-4">
      <header className="mb-4 flex flex-wrap items-center gap-4">
        <div>
          <h1 className="text-xl font-bold">DreamGuard</h1>
          <p className="text-xs text-slate-400">Safety supervisor for Dream-1 robot actions</p>
        </div>
        <nav className="flex gap-1 rounded-lg bg-slate-900 p-1" aria-label="Pages">
          {(Object.keys(TABS) as Tab[]).map((key) => (
            <button
              key={key}
              type="button"
              aria-current={tab === key ? "page" : undefined}
              onClick={() => select(key)}
              className={`rounded-md px-3 py-1.5 text-sm transition ${
                tab === key ? "bg-slate-700 text-white" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {TABS[key]}
            </button>
          ))}
        </nav>
        <span className="ml-auto flex items-center gap-2 text-xs text-slate-400" role="status">
          <span className={`h-2 w-2 rounded-full ${connection.dot}`} />
          {connection.label}
        </span>
      </header>
      <main>
        {tab === "live" && <LivePage stream={stream} />}
        {tab === "sessions" && <SessionsPage onReplayStarted={() => select("live")} />}
        {tab === "profile" && <ProfilePage />}
      </main>
      <footer className="mt-6 text-center text-[11px] text-slate-600">
        Development and simulation safety layer — not a certified safety controller.
      </footer>
    </div>
  );
}
