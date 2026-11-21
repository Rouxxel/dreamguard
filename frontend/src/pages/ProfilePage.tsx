import { useCatalog, useProfile } from "../api/hooks";
import { ARMS } from "../api/types";
import { Empty, ErrorNote, Panel } from "../components/ui";

const LABELS: Record<string, string> = {
  action_hz: "Action rate (rows / s)",
  max_joint_step_rad: "Max joint step per row (rad)",
  max_joint_velocity_rad_s: "Max joint velocity (rad/s)",
  near_limit_margin_rad: "Near-limit warning margin (rad)",
  gripper_range: "Gripper range",
  require_current_state: "Measured state required",
  min_rows: "Min rows per chunk",
  max_rows: "Max rows per chunk",
  require_workspace_check: "Workspace check required",
  workspace_min_m: "Workspace min (m)",
  workspace_max_m: "Workspace max (m)",
  minimum_tool_separation_m: "Min gripper separation (m)",
};

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "off";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (Array.isArray(value)) return `[${value.map((v) => formatValue(v)).join(", ")}]`;
  return String(value);
}

export function ProfilePage() {
  const profile = useProfile();
  const catalog = useCatalog();
  if (profile.error) return <ErrorNote error={profile.error} />;
  if (!profile.data) return <Empty>Loading profile…</Empty>;

  const { config } = profile.data;
  const limits = config.joint_limits as Record<string, number[][]>;
  const names = catalog.data?.joint_names ?? [];

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title={`Profile: ${profile.data.name}`}>
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
          {Object.entries(LABELS).map(([key, label]) => (
            <div key={key} className="contents">
              <dt className="text-slate-400">{label}</dt>
              <dd className="font-mono">{formatValue(config[key])}</dd>
            </div>
          ))}
          <dt className="text-slate-400">Forward kinematics</dt>
          <dd className="font-mono">{profile.data.forward_kinematics ? "simulator" : "none"}</dd>
          <dt className="text-slate-400">Blocks in a row before halt</dt>
          <dd className="font-mono">{profile.data.max_consecutive_blocks}</dd>
        </dl>
      </Panel>
      <Panel title="Joint limits (rad)">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-400">
            <tr>
              <th className="py-1">Joint</th>
              {ARMS.map((arm) => (
                <th key={arm} className="py-1 capitalize">
                  {arm} arm
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="font-mono">
            {(limits.right ?? []).map((_, joint) => (
              <tr key={joint} className="border-t border-slate-800">
                <td className="py-1 font-sans text-slate-300">{names[joint] ?? `joint${joint + 1}`}</td>
                {ARMS.map((arm) => {
                  const [low, high] = limits[arm]?.[joint] ?? [];
                  return (
                    <td key={arm} className="py-1">
                      [{low?.toFixed(3)}, {high?.toFixed(3)}]
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-slate-500">
          Read-only. Limits come from the backend's active safety profile; they are development
          guardrails, not certified safety limits.
        </p>
      </Panel>
    </div>
  );
}
