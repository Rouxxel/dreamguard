import type { ReactNode } from "react";

import { DECISION_STYLES, type Decision } from "../lib/format";

export function Panel({
  title,
  actions,
  children,
  className = "",
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-slate-800 bg-slate-900/70 p-4 ${className}`}>
      <header className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">{title}</h2>
        {actions}
      </header>
      {children}
    </section>
  );
}

export function DecisionBadge({ decision }: { decision: Decision }) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-bold ring-1 ring-inset ${DECISION_STYLES[decision]}`}
    >
      {decision}
    </span>
  );
}

export function Button({
  children,
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "danger" | "ghost";
}) {
  const styles = {
    primary: "bg-sky-600 hover:bg-sky-500 text-white",
    danger: "bg-rose-600 hover:bg-rose-500 text-white",
    ghost: "bg-slate-800 hover:bg-slate-700 text-slate-200",
  }[variant];
  return (
    <button
      type="button"
      className={`rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${styles}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : String(error);
  return (
    <p role="alert" className="mt-2 rounded-md bg-rose-950/60 px-3 py-2 text-sm text-rose-200">
      {message}
    </p>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-slate-500">{children}</p>;
}
