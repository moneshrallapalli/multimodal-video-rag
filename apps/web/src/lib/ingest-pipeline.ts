/** Display graph for admin ingestion. Maps worker Job.stage onto cockpit nodes. */

import type { CockpitColumn, CockpitRuntime } from "./cockpit";
import type { IngestStage, Job, JobStatus } from "./types";

export type IngestNodeId =
  | "queue_job"
  | "fetch_metadata"
  | "download_video"
  | "extract_audio"
  | "extract_frames"
  | "caption_frames"
  | "transcribe"
  | "embed_upsert"
  | "refresh_bm25"
  | "write_catalog"
  | "complete";

export const INGEST_COLUMNS: CockpitColumn<IngestNodeId>[] = [
  {
    id: "queue",
    label: "QUEUE",
    tint: "blue",
    nodes: [
      { id: "queue_job", label: "Queue job", detail: "API · SQS" },
      { id: "fetch_metadata", label: "Fetch metadata", detail: "yt-dlp meta" },
    ],
  },
  {
    id: "media",
    label: "MEDIA",
    tint: "gold",
    nodes: [
      { id: "download_video", label: "Download video", detail: "yt-dlp" },
      { id: "extract_audio", label: "Extract audio", detail: "ffmpeg" },
      { id: "extract_frames", label: "Extract frames", detail: "ffmpeg" },
    ],
  },
  {
    id: "speech",
    label: "SPEECH",
    tint: "gold",
    nodes: [
      { id: "caption_frames", label: "Caption frames", detail: "optional" },
      { id: "transcribe", label: "Transcribe", detail: "Whisper" },
    ],
  },
  {
    id: "index",
    label: "INDEX",
    tint: "purple",
    nodes: [
      { id: "embed_upsert", label: "Embed + upsert", detail: "Titan · Pinecone" },
      { id: "refresh_bm25", label: "Refresh BM25", detail: "corpus stats" },
    ],
  },
  {
    id: "catalog",
    label: "CATALOG",
    tint: "purple",
    nodes: [
      { id: "write_catalog", label: "Write catalog", detail: "DynamoDB" },
      { id: "complete", label: "Complete", detail: "searchable" },
    ],
  },
];

export const INGEST_EDGES: [IngestNodeId, IngestNodeId][] = [
  ["queue_job", "fetch_metadata"],
  ["fetch_metadata", "download_video"],
  ["download_video", "extract_audio"],
  ["extract_audio", "extract_frames"],
  ["extract_frames", "caption_frames"],
  ["caption_frames", "transcribe"],
  ["transcribe", "embed_upsert"],
  ["embed_upsert", "refresh_bm25"],
  ["refresh_bm25", "write_catalog"],
  ["write_catalog", "complete"],
];

export const INGEST_NODE_ORDER: IngestNodeId[] = INGEST_COLUMNS.flatMap((column) =>
  column.nodes.map((node) => node.id),
);

const OPTIONAL_NODES = new Set<IngestNodeId>(["caption_frames", "refresh_bm25"]);

const STAGE_TO_NODE: Record<IngestStage, IngestNodeId> = {
  queued: "queue_job",
  fetch_metadata: "fetch_metadata",
  download_video: "download_video",
  extract_audio: "extract_audio",
  extract_frames: "extract_frames",
  caption_frames: "caption_frames",
  transcribe: "transcribe",
  embed_upsert: "embed_upsert",
  refresh_bm25: "refresh_bm25",
  write_catalog: "write_catalog",
  completed: "complete",
};

const NODE_SUMMARY: Record<IngestNodeId, string> = {
  queue_job: "Job written to DynamoDB and sent to SQS",
  fetch_metadata: "Reading YouTube title and duration",
  download_video: "Downloading the source video",
  extract_audio: "Extracting the audio track",
  extract_frames: "Sampling visual frames",
  caption_frames: "Captioning sampled frames",
  transcribe: "Transcribing speech with Whisper",
  embed_upsert: "Embedding artifacts and upserting Pinecone",
  refresh_bm25: "Refreshing corpus BM25 stats",
  write_catalog: "Writing the searchable video record",
  complete: "Video is searchable",
};

export interface IngestNodeState extends CockpitRuntime {
  summary: string;
}

const IDLE: IngestNodeState = { status: "idle", metric: "", summary: "" };

export function emptyIngestNodes(): Record<IngestNodeId, IngestNodeState> {
  return Object.fromEntries(INGEST_NODE_ORDER.map((id) => [id, { ...IDLE }])) as Record<
    IngestNodeId,
    IngestNodeState
  >;
}

export function isIngestStage(value: string | null | undefined): value is IngestStage {
  return Boolean(value && value in STAGE_TO_NODE);
}

export function currentIngestNode(job: Job): IngestNodeId {
  if (isIngestStage(job.stage) && !isStaleStage(job)) {
    return STAGE_TO_NODE[job.stage];
  }
  return inferNodeFromStatus(job.status, job.progress);
}

/** Old workers only update coarse status/progress; ignore a lagging stage field. */
function isStaleStage(job: Job): boolean {
  if (!isIngestStage(job.stage)) return false;
  if (job.stage === "queued" && job.status !== "queued") return true;
  if (job.stage === "completed" && job.status !== "completed") return true;
  if (
    job.status === "failed" &&
    job.stage !== "completed" &&
    STAGE_TO_NODE[job.stage] !== inferNodeFromStatus(job.status, job.progress)
  ) {
    return true;
  }
  return false;
}

function inferNodeFromStatus(status: JobStatus, progress: number): IngestNodeId {
  switch (status) {
    case "queued":
      return "queue_job";
    case "downloading":
      if (progress < 25) return "fetch_metadata";
      if (progress < 40) return "download_video";
      if (progress < 50) return "extract_audio";
      return "extract_frames";
    case "transcribing":
      return "transcribe";
    case "embedding":
      if (progress < 90) return "embed_upsert";
      if (progress < 96) return "refresh_bm25";
      return "write_catalog";
    case "completed":
      return "complete";
    case "failed":
      if (progress < 25) return "fetch_metadata";
      if (progress < 40) return "download_video";
      if (progress < 50) return "extract_audio";
      if (progress < 70) return "extract_frames";
      if (progress < 85) return "transcribe";
      return "embed_upsert";
  }
}

export function reduceIngestJob(job: Job | null): Record<IngestNodeId, IngestNodeState> {
  const state = emptyIngestNodes();
  if (!job) return state;

  const current = currentIngestNode(job);
  const currentIdx = INGEST_NODE_ORDER.indexOf(current);
  const seen = new Set<IngestNodeId>();
  for (const stage of job.stages_seen ?? []) {
    if (isIngestStage(stage)) seen.add(STAGE_TO_NODE[stage]);
  }
  seen.add(current);
  if (job.status !== "queued") seen.add("queue_job");

  for (let i = 0; i < INGEST_NODE_ORDER.length; i += 1) {
    const id = INGEST_NODE_ORDER[i];
    if (i > currentIdx) continue;
    if (id === current) {
      if (job.status === "failed") {
        state[id] = { status: "failed", metric: "FAIL", summary: job.error || NODE_SUMMARY[id] };
      } else if (job.status === "completed") {
        state[id] = { status: "ok", metric: "OK", summary: NODE_SUMMARY[id] };
      } else if (job.status === "queued") {
        state[id] = { status: "started", metric: "WAIT", summary: "Waiting for the Fargate worker" };
      } else {
        state[id] = {
          status: "started",
          metric: `${job.progress}%`,
          summary: NODE_SUMMARY[id],
        };
      }
      continue;
    }
    if (OPTIONAL_NODES.has(id) && !seen.has(id)) {
      state[id] = { status: "skipped", metric: "skip", summary: "This worker skipped this step" };
    } else {
      state[id] = { status: "ok", metric: "OK", summary: NODE_SUMMARY[id] };
    }
  }

  return state;
}

export function ingestHealthCounts(nodes: Record<IngestNodeId, IngestNodeState>) {
  const counts = { ok: 0, skipped: 0, failed: 0, active: 0 };
  for (const node of Object.values(nodes)) {
    if (node.status === "ok") counts.ok += 1;
    else if (node.status === "skipped") counts.skipped += 1;
    else if (node.status === "failed") counts.failed += 1;
    else if (node.status === "started") counts.active += 1;
  }
  return counts;
}

export function ingestNodeLabel(id: IngestNodeId): string {
  for (const column of INGEST_COLUMNS) {
    const node = column.nodes.find((item) => item.id === id);
    if (node) return node.label;
  }
  return id;
}

export function ingestLogLines(job: Job | null): Array<{
  ts: string;
  node: string;
  summary: string;
  tone: "ok" | "fail" | "live" | "skip";
}> {
  if (!job) return [];
  const seen = job.stages_seen?.length ? job.stages_seen : [job.stage ?? job.status];
  return seen.map((stage, index) => {
    const node = isIngestStage(stage) ? STAGE_TO_NODE[stage] : currentIngestNode(job);
    const last = index === seen.length - 1;
    const failed = last && job.status === "failed";
    return {
      ts: index === 0 ? job.created_at : last ? job.updated_at : "",
      node: isIngestStage(stage) ? stage : node,
      summary: failed ? job.error || "failed" : NODE_SUMMARY[node],
      tone: failed ? "fail" : last && job.status !== "completed" ? "live" : "ok",
    };
  });
}

export function isActiveJob(job: Job): boolean {
  return (
    job.status === "queued" ||
    job.status === "downloading" ||
    job.status === "transcribing" ||
    job.status === "embedding"
  );
}
