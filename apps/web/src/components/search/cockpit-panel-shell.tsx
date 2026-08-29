"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type CockpitHealthTone = "ok" | "skip" | "fail" | "live";

export interface CockpitHealthRow {
  label: string;
  value: number;
  tone: CockpitHealthTone;
}

export function CockpitPanelShell({
  ariaLabel,
  health,
  running,
  statusLabel,
  statusDetail,
  graph,
  detail,
  logTitle,
  log,
}: {
  ariaLabel: string;
  health: CockpitHealthRow[];
  running: boolean;
  statusLabel: string;
  statusDetail: string;
  graph: ReactNode;
  detail: ReactNode;
  logTitle: string;
  log: ReactNode;
}) {
  return (
    <section className="pipeline-cockpit overflow-hidden rounded-2xl" aria-label={ariaLabel}>
      <div className="pipeline-cockpit-header flex flex-wrap items-center justify-between gap-3 border-b border-[var(--pipe-border)] px-4 py-3">
        <div>
          <p className="text-sm font-medium text-[var(--pipe-text)]">Live pipeline</p>
          <p className="text-xs text-[var(--pipe-text-muted)]">
            Real backend stages · click a node to inspect
          </p>
        </div>
        <div
          className={cn(
            "inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-[10px] tracking-[0.14em] uppercase",
            running
              ? "border-[var(--pipe-live)]/30 bg-[var(--pipe-live)]/10 text-[var(--pipe-live)]"
              : "border-[var(--pipe-ok)]/30 bg-[var(--pipe-ok)]/10 text-[var(--pipe-ok)]",
          )}
        >
          <span
            className={cn(
              "size-1.5 rounded-full",
              running ? "bg-[var(--pipe-live)] animate-pulse" : "bg-[var(--pipe-ok)]",
            )}
            aria-hidden
          />
          {statusLabel}
        </div>
      </div>

      <div className="grid gap-0 lg:grid-cols-[8.5rem_minmax(0,1fr)_17.5rem]">
        <aside className="flex flex-col justify-between border-b border-[var(--pipe-border)] bg-[var(--pipe-surface-muted)]/50 px-3 py-3 lg:border-r lg:border-b-0">
          <div>
            <div className="pipe-section-label">Health</div>
            <dl className="mt-3 space-y-2 font-mono text-[11px]">
              {health.map((row) => (
                <HealthRow key={row.label} {...row} />
              ))}
            </dl>
          </div>
          <div className="mt-4 font-mono text-[11px] text-[var(--pipe-text-muted)]">
            <div className="pipe-status-detail">{statusDetail}</div>
          </div>
        </aside>

        <div className="min-w-0 overflow-x-auto border-b border-[var(--pipe-border)] px-2 py-4 lg:border-b-0">
          {graph}
        </div>

        <aside className="min-h-[16rem] border-[var(--pipe-border)] bg-[var(--pipe-surface-muted)]/30 px-3 py-3 lg:border-l">
          {detail}
        </aside>
      </div>

      <div className="border-t border-[var(--pipe-border)] bg-[var(--pipe-surface-muted)]/40 px-4 py-2.5">
        <div className="pipe-section-label">{logTitle}</div>
        {log}
      </div>
    </section>
  );
}

function HealthRow({ label, value, tone }: CockpitHealthRow) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-[var(--pipe-text-muted)]">{label}</dt>
      <dd className={cn("text-base tabular-nums", healthToneClass(tone))}>{value}</dd>
    </div>
  );
}

export function healthToneClass(tone: CockpitHealthTone): string {
  switch (tone) {
    case "ok":
      return "text-[var(--pipe-ok)]";
    case "skip":
      return "text-[var(--pipe-text-muted)]";
    case "fail":
      return "text-[var(--pipe-fail)]";
    case "live":
      return "text-[var(--pipe-live)]";
  }
}

export function CockpitDetailMetric({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-lg border border-[var(--pipe-border)] bg-[var(--pipe-surface)] px-2 py-1.5">
      <div className="pipe-metric-label">{label}</div>
      <div className="mt-0.5 truncate font-mono text-sm text-[var(--pipe-text)]">{value}</div>
    </div>
  );
}

export function CockpitDetailEmpty({ children }: { children: ReactNode }) {
  return (
    <div className="font-mono text-[11px] leading-relaxed text-[var(--pipe-text-muted)]">
      {children}
    </div>
  );
}
