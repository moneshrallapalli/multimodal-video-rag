"use client";

import { useMemo, useState } from "react";
import { useReducedMotion } from "motion/react";

import { CockpitGraph } from "@/components/search/cockpit-graph";
import {
  CockpitDetailEmpty,
  CockpitDetailMetric,
  CockpitPanelShell,
} from "@/components/search/cockpit-panel-shell";
import {
  INGEST_COLUMNS,
  INGEST_EDGES,
  currentIngestNode,
  ingestHealthCounts,
  ingestLogLines,
  ingestNodeLabel,
  isActiveJob,
  reduceIngestJob,
  type IngestNodeId,
} from "@/lib/ingest-pipeline";
import { formatClock } from "@/lib/pipeline";
import type { Job } from "@/lib/types";

export function IngestPipelinePanel({ job }: { job: Job | null }) {
  const reduceMotion = useReducedMotion() ?? false;
  const nodes = useMemo(() => reduceIngestJob(job), [job]);
  const followId = job ? currentIngestNode(job) : null;
  const [pinnedId, setPinnedId] = useState<IngestNodeId | null>(null);
  const selectedId = pinnedId && nodes[pinnedId] ? pinnedId : followId;
  const health = ingestHealthCounts(nodes);
  const selected = selectedId ? nodes[selectedId] : null;
  const logLines = ingestLogLines(job);
  const running = job ? isActiveJob(job) : false;

  return (
    <CockpitPanelShell
      ariaLabel="Live ingestion pipeline"
      running={running}
      statusLabel={running ? "Live" : "Settled"}
      statusDetail={
        job ? `${job.progress}% · worker stages` : "Select a job below to inspect the path"
      }
      health={[
        { label: "OK", value: health.ok, tone: "ok" },
        { label: "Skipped", value: health.skipped, tone: "skip" },
        { label: "Failed", value: health.failed, tone: "fail" },
        { label: "Active", value: health.active, tone: "live" },
      ]}
      graph={
        <CockpitGraph
          columns={INGEST_COLUMNS}
          edges={INGEST_EDGES}
          nodes={nodes}
          selectedId={selectedId}
          onSelect={setPinnedId}
          reduceMotion={reduceMotion}
        />
      }
      detail={<IngestDetail job={job} nodeId={selectedId} runtime={selected} />}
      logTitle="Worker log"
      log={
        <ol
          className="mt-1.5 max-h-32 space-y-0.5 overflow-y-auto font-mono text-[11px] leading-5"
          aria-live="polite"
        >
          {logLines.length === 0 ? (
            <li className="pipe-log-summary-muted">
              Queue a YouTube URL to watch download, Whisper, frames, and Pinecone upsert.
            </li>
          ) : (
            logLines.map((line, index) => (
              <li key={`${line.node}-${index}`}>
                <span className="pipe-log-time">
                  {line.ts ? formatClock(line.ts) : "··:··:··"}
                </span>{" "}
                <span
                  className={
                    line.tone === "fail"
                      ? "pipe-log-node-fail"
                      : line.tone === "live"
                        ? "pipe-log-node-live"
                        : "pipe-log-node-ok"
                  }
                >
                  {line.node}
                </span>{" "}
                <span
                  className={
                    line.tone === "fail" ? "pipe-log-summary-fail" : "pipe-log-summary"
                  }
                >
                  {line.summary}
                </span>
              </li>
            ))
          )}
        </ol>
      }
    />
  );
}

function IngestDetail({
  job,
  nodeId,
  runtime,
}: {
  job: Job | null;
  nodeId: IngestNodeId | null;
  runtime: ReturnType<typeof reduceIngestJob>[IngestNodeId] | null;
}) {
  if (!job || !nodeId || !runtime) {
    return (
      <CockpitDetailEmpty>
        Select a job in the table to inspect the worker path.
      </CockpitDetailEmpty>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="pipe-section-label">Selected node</div>
      <div className="mt-1 font-mono text-sm text-[var(--pipe-text)]">{ingestNodeLabel(nodeId)}</div>
      <div className="font-mono text-[10px] text-[var(--pipe-text-muted)]">{nodeId}</div>
      <div className="mt-2 font-mono text-[11px] text-[var(--pipe-text-muted)]">
        {runtime.status.toUpperCase()}
      </div>
      {runtime.summary ? (
        <p className="mt-2 font-mono text-[11px] leading-relaxed text-[var(--pipe-text)]">
          {runtime.summary}
        </p>
      ) : null}

      <div className="mt-4 grid grid-cols-3 gap-2">
        <CockpitDetailMetric label="Status" value={job.status} />
        <CockpitDetailMetric label="Stage" value={job.stage ?? "—"} />
        <CockpitDetailMetric label="Pct" value={`${job.progress}%`} />
      </div>

      <div className="mt-4 pipe-section-label">Job</div>
      <p className="mt-1.5 font-mono text-[11px] leading-relaxed text-[var(--pipe-text)]">
        {job.title ?? job.youtube_url}
      </p>
      {job.video_id ? (
        <p className="mt-1 font-mono text-[10px] text-[var(--pipe-text-muted)]">{job.video_id}</p>
      ) : null}
      {job.error ? (
        <p className="mt-3 font-mono text-[11px] leading-relaxed pipe-metric-fail">{job.error}</p>
      ) : null}
    </div>
  );
}
