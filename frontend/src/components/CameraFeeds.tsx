import { useState } from "react";

import { cameraUrl } from "../api/client";

function CameraView({ camera, label }: { camera: string; label: string }) {
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  return (
    <figure className="relative overflow-hidden rounded-lg bg-black">
      {failed ? (
        <div className="flex aspect-[320/176] flex-col items-center justify-center gap-2 text-xs text-slate-400">
          Camera unavailable
          <button
            type="button"
            className="rounded bg-slate-800 px-2 py-1 text-slate-200 hover:bg-slate-700"
            onClick={() => {
              setFailed(false);
              setAttempt((a) => a + 1);
            }}
          >
            Retry
          </button>
        </div>
      ) : (
        <img
          key={attempt}
          src={`${cameraUrl(camera)}?v=${attempt}`}
          alt={`${label} camera`}
          className="aspect-[320/176] w-full object-cover"
          onError={() => setFailed(true)}
        />
      )}
      <figcaption className="absolute left-2 top-2 rounded bg-black/60 px-1.5 py-0.5 text-[11px] text-slate-200">
        {label}
      </figcaption>
    </figure>
  );
}

export function CameraFeeds({ cameras }: { cameras: Record<string, string> | undefined }) {
  const entries = Object.entries(cameras ?? { overhead: "Overhead" });
  const [main, ...others] = entries;
  return (
    <div className="space-y-2">
      {main && <CameraView camera={main[0]} label={main[1]} />}
      <div className="grid grid-cols-2 gap-2">
        {others.map(([camera, label]) => (
          <CameraView key={camera} camera={camera} label={label} />
        ))}
      </div>
    </div>
  );
}
