"use client";

import { useMemo, useState } from "react";
import { useReducedMotion } from "motion/react";

import { mmss } from "@/lib/format";
import {
  asHits,
  asNum,
  displayNodeForEvent,
  formatClock,
  healthCounts,
  nodeLabel,
  reducePipelineEvents,
  scoreFromPayload,
  type DisplayNodeId,
} from "@/lib/pipeline";
import type { PipelineEvent } from "@/lib/types";

import {
  CockpitDetailEmpty,
  CockpitDetailMetric,
  CockpitPanelShell,
} from "./cockpit-panel-shell";
import { PipelineGraph } from "./pipeline-graph";

export function PipelinePanel({
  events,
  running,
}: {
  events: PipelineEvent[];
  running: boolean;
}) {
  const reduceMotion = useReducedMotion() ?? false;
  const nodes = useMemo(() => reducePipelineEvents(events), [events]);
  const followId = useMemo(() => followLatestNode(events, nodes), [events, nodes]);
  const [pinnedId, setPinnedId] = useState<DisplayNodeId | null>(null);
  const selectedId = pinnedId ?? followId;
  const health = healthCounts(nodes);
  const selected = selectedId ? nodes[selectedId] : null;
  const logLines = events.filter((event) => event.status !== "started");

  return (
    <CockpitPanelShell
      ariaLabel="Live query pipeline"
      running={running}
      statusLabel={running ? "Live" : "Settled"}
      statusDetail={running ? "1.0x · streaming node events" : "Run complete · real events"}
      health={[
        { label: "OK", value: health.ok, tone: "ok" },
        { label: "Skipped", value: health.skipped, tone: "skip" },
        { label: "Refused", value: health.refused, tone: "fail" },
        { label: "Active", value: health.active, tone: "live" },
      ]}
      graph={
        <PipelineGraph
          nodes={nodes}
          selectedId={selectedId}
          onSelect={setPinnedId}
          reduceMotion={reduceMotion}
        />
      }
      detail={<PipelineDetail nodeId={selectedId} runtime={selected} />}
      logTitle="Orchestrator log"
      log={
        <ol
          className="mt-1.5 max-h-32 space-y-0.5 overflow-y-auto font-mono text-[11px] leading-5"
          aria-live="polite"
        >
          {logLines.length === 0 ? (
            <li className="pipe-log-summary-muted">Waiting for the first node event.</li>
          ) : (
            logLines.map((event, index) => (
              <li key={`${event.run_id}-${event.node}-${event.status}-${index}`}>
                <span className="pipe-log-time">{formatClock(event.ts)}</span>{" "}
                <span className={logNodeClass(event.status)}>{event.node}</span>{" "}
                <span className={logStatusClass(event.status)}>{event.summary}</span>
              </li>
            ))
          )}
        </ol>
      }
    />
  );
}

function followLatestNode(
  events: PipelineEvent[],
  nodes: Record<DisplayNodeId, ReturnType<typeof reducePipelineEvents>[DisplayNodeId]>,
): DisplayNodeId | null {
  const latest = [...events].reverse().find((event) => event.status !== "started");
  if (!latest) return events.length ? "user_search" : null;
  return displayNodeForEvent(latest, nodes);
}

function PipelineDetail({
  nodeId,
  runtime,
}: {
  nodeId: DisplayNodeId | null;
  runtime: ReturnType<typeof reducePipelineEvents>[DisplayNodeId] | null;
}) {
  if (!nodeId || !runtime) {
    return (
      <CockpitDetailEmpty>
        Click a node to inspect the live payload from this run.
      </CockpitDetailEmpty>
    );
  }

  const payload = runtime.event?.payload ?? {};
  const hits = asHits(payload);
  const intent = typeof payload.intent === "string" ? payload.intent : null;
  const rewritten =
    typeof payload.rewritten_query === "string" ? payload.rewritten_query : null;
  const preview =
    typeof payload.answer_preview === "string" ? payload.answer_preview : null;

  return (
    <div className="flex h-full flex-col">
      <div className="pipe-section-label">Selected node</div>
      <div className="mt-1 font-mono text-sm text-[var(--pipe-text)]">{nodeLabel(nodeId)}</div>
      <div className="font-mono text-[10px] text-[var(--pipe-text-muted)]">{nodeId}</div>
      <div className="mt-2 font-mono text-[11px] text-[var(--pipe-text-muted)]">
        {runtime.status.toUpperCase()}
        {runtime.durationMs != null && runtime.durationMs > 0
          ? ` · ${Math.round(runtime.durationMs)}ms`
          : ""}
      </div>
      {runtime.summary ? (
        <p className="mt-2 font-mono text-[11px] leading-relaxed text-[var(--pipe-text)]">
          {runtime.summary}
        </p>
      ) : null}

      <div className="mt-4 grid grid-cols-3 gap-2">
        <CockpitDetailMetric
          label="Hits"
          value={
            asNum(payload.hit_count) ??
            asNum(payload.fused_count) ??
            (hits.length || "—")
          }
        />
        <CockpitDetailMetric
          label="Score"
          value={scoreFromPayload(payload) ?? "—"}
        />
        <CockpitDetailMetric
          label="Lag"
          value={
            runtime.durationMs != null && runtime.durationMs > 0
              ? `${Math.round(runtime.durationMs)}ms`
              : "—"
          }
        />
      </div>

      {intent ? (
        <div className="mt-3 font-mono text-[11px] text-[var(--pipe-text)]">intent {intent}</div>
      ) : null}
      {rewritten ? (
        <div className="mt-3 font-mono text-[11px] leading-relaxed text-[var(--pipe-active)]">
          rewritten: {rewritten}
        </div>
      ) : null}
      {preview ? (
        <div className="mt-3 font-mono text-[11px] leading-relaxed text-[var(--pipe-text)]">
          {preview}
        </div>
      ) : null}
      {payload.passed === false ? (
        <div className="mt-3 font-mono text-[11px] pipe-metric-fail">
          gate refused{typeof payload.reason === "string" ? ` · ${payload.reason}` : ""}
        </div>
      ) : null}

      <div className="mt-4 pipe-section-label">Sample rows · live</div>
      {hits.length ? (
        <table className="mt-1.5 w-full font-mono text-[10px] text-[var(--pipe-text)]">
          <thead>
            <tr className="text-[var(--pipe-text-muted)]">
              <th className="pb-1 text-left font-normal">TS</th>
              <th className="pb-1 text-left font-normal">Video</th>
              <th className="pb-1 text-right font-normal">Score</th>
            </tr>
          </thead>
          <tbody>
            {hits.map((hit, index) => (
              <tr key={`${hit.video_id}-${hit.start_seconds}-${index}`}>
                <td className="py-0.5 text-[var(--pipe-live)]">{mmss(hit.start_seconds)}</td>
                <td className="max-w-[7rem] truncate py-0.5">{hit.video_id}</td>
                <td className="py-0.5 text-right text-[var(--pipe-active)]">
                  {(() => {
                    const score = asNum(hit.score);
                    return score != null ? score.toFixed(2) : "—";
                  })()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="mt-1.5 font-mono text-[10px] text-[var(--pipe-text-muted)]">
          {runtime.event ? "No retrieval rows on this node." : "No event yet for this node."}
        </p>
      )}
      {hits[0]?.snippet ? (
        <p className="mt-2 line-clamp-4 font-mono text-[10px] leading-relaxed text-[var(--pipe-text-muted)]">
          {hits[0].snippet}
        </p>
      ) : null}
    </div>
  );
}

function logNodeClass(status: PipelineEvent["status"]): string {
  if (status === "refused" || status === "failed") return "pipe-log-node-fail";
  if (status === "retry") return "pipe-log-node-retry";
  if (status === "ok") return "pipe-log-node-ok";
  return "pipe-log-summary-muted";
}

function logStatusClass(status: PipelineEvent["status"]): string {
  if (status === "refused" || status === "failed") return "pipe-log-summary-fail";
  if (status === "skipped") return "pipe-log-summary-muted";
  return "pipe-log-summary";
}
