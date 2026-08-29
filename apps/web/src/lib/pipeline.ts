/** Display graph for the live query pipeline. Maps LangGraph events onto UI nodes. */

import type { CockpitTint } from "./cockpit";
import type { PipelineEvent, PipelineEventStatus, PipelineHitSnippet } from "./types";

export type DisplayNodeId =
  | "user_search"
  | "validate_query"
  | "classify_intent"
  | "embed_transcript"
  | "retrieve_transcript"
  | "embed_visual"
  | "retrieve_visual"
  | "rrf_fuse"
  | "cross_encoder_rerank"
  | "apply_retrieval_gate"
  | "rewrite_query"
  | "retrieve_again"
  | "build_context"
  | "generate_answer"
  | "citations"
  | "refuse_if_weak";

export type ColumnId = "query" | "retrieve" | "fuse" | "retry" | "answer";
export type ColumnTint = CockpitTint;

export interface DisplayNode {
  id: DisplayNodeId;
  label: string;
  detail: string;
}

export interface PipelineColumn {
  id: ColumnId;
  label: string;
  tint: ColumnTint;
  nodes: DisplayNode[];
}

export const PIPELINE_COLUMNS: PipelineColumn[] = [
  {
    id: "query",
    label: "QUERY",
    tint: "blue",
    nodes: [
      { id: "user_search", label: "User search", detail: "user_search" },
      { id: "validate_query", label: "Validate", detail: "validate_query" },
      { id: "classify_intent", label: "Classify intent", detail: "classify_intent" },
    ],
  },
  {
    id: "retrieve",
    label: "RETRIEVE",
    tint: "gold",
    nodes: [
      { id: "embed_transcript", label: "Embed text", detail: "embed_transcript · Titan v2" },
      { id: "retrieve_transcript", label: "Transcript index", detail: "retrieve_transcript · dotproduct" },
      { id: "embed_visual", label: "Embed visual", detail: "embed_visual · Titan G1" },
      { id: "retrieve_visual", label: "Visual index", detail: "retrieve_visual · cosine" },
    ],
  },
  {
    id: "fuse",
    label: "FUSE",
    tint: "gold",
    nodes: [
      { id: "rrf_fuse", label: "RRF fuse", detail: "rrf_fuse" },
      { id: "cross_encoder_rerank", label: "Cross-encoder", detail: "video-rag-reranker" },
      { id: "apply_retrieval_gate", label: "Retrieval gate", detail: "apply_retrieval_gate" },
    ],
  },
  {
    id: "retry",
    label: "RETRY",
    tint: "red",
    nodes: [
      { id: "rewrite_query", label: "Rewrite query", detail: "rewrite_query" },
      { id: "retrieve_again", label: "Retrieve again", detail: "retrieve_again" },
    ],
  },
  {
    id: "answer",
    label: "ANSWER",
    tint: "purple",
    nodes: [
      { id: "build_context", label: "Build context", detail: "build_context" },
      { id: "generate_answer", label: "Generate", detail: "generate_answer · Haiku" },
      { id: "citations", label: "Citations", detail: "citations" },
      { id: "refuse_if_weak", label: "Refuse if weak", detail: "refuse_if_weak" },
    ],
  },
];

export const PIPELINE_EDGES: [DisplayNodeId, DisplayNodeId][] = [
  ["user_search", "validate_query"],
  ["validate_query", "classify_intent"],
  ["classify_intent", "embed_transcript"],
  ["classify_intent", "embed_visual"],
  ["embed_transcript", "retrieve_transcript"],
  ["embed_visual", "retrieve_visual"],
  ["retrieve_transcript", "rrf_fuse"],
  ["retrieve_visual", "rrf_fuse"],
  ["rrf_fuse", "cross_encoder_rerank"],
  ["cross_encoder_rerank", "apply_retrieval_gate"],
  ["apply_retrieval_gate", "build_context"],
  ["apply_retrieval_gate", "rewrite_query"],
  ["rewrite_query", "retrieve_again"],
  ["retrieve_again", "rrf_fuse"],
  ["build_context", "generate_answer"],
  ["generate_answer", "citations"],
  ["generate_answer", "refuse_if_weak"],
];

export type NodeRuntimeStatus = "idle" | PipelineEventStatus;

export interface NodeRuntimeState {
  status: NodeRuntimeStatus;
  durationMs: number | null;
  summary: string;
  metric: string;
  event: PipelineEvent | null;
}

export function emptyNodeStates(): Record<DisplayNodeId, NodeRuntimeState> {
  const idle: NodeRuntimeState = {
    status: "idle",
    durationMs: null,
    summary: "",
    metric: "",
    event: null,
  };
  return Object.fromEntries(
    PIPELINE_COLUMNS.flatMap((column) => column.nodes.map((node) => [node.id, { ...idle }])),
  ) as Record<DisplayNodeId, NodeRuntimeState>;
}

export function reducePipelineEvents(
  events: PipelineEvent[],
): Record<DisplayNodeId, NodeRuntimeState> {
  const state = emptyNodeStates();
  if (events.length) {
    writeNode(state, "user_search", events[0], "ok", "query in", "IN");
  }
  for (const event of events) {
    applyEvent(state, event);
  }
  return state;
}

function applyEvent(state: Record<DisplayNodeId, NodeRuntimeState>, event: PipelineEvent) {
  const metric = metricFor(event);
  switch (event.node) {
    case "validate_query":
      writeNode(state, "validate_query", event, event.status, event.summary, metric);
      if (event.status === "started") {
        writeNode(state, "user_search", event, "ok", "query in", "IN");
      }
      break;
    case "classify_intent":
      writeNode(state, "classify_intent", event, event.status, event.summary, metric);
      break;
    case "retrieve_transcript":
      writeNode(state, "embed_transcript", event, embedStatus(event.status), event.summary, metric);
      writeNode(state, "retrieve_transcript", event, event.status, event.summary, metric);
      if (event.status === "retry") {
        writeNode(state, "retrieve_again", event, "retry", event.summary, "RETRY");
      }
      break;
    case "retrieve_visual":
      writeNode(state, "embed_visual", event, embedStatus(event.status), event.summary, metric);
      writeNode(state, "retrieve_visual", event, event.status, event.summary, metric);
      if (event.status === "retry") {
        writeNode(state, "retrieve_again", event, "retry", event.summary, "RETRY");
      }
      break;
    case "fuse_results":
      writeNode(state, "rrf_fuse", event, event.status, event.summary, metric);
      if (event.status === "started") {
        writeNode(state, "cross_encoder_rerank", event, "started", "rerank?", "");
      } else if (event.status === "ok") {
        const reranked = Boolean(event.payload.reranked);
        writeNode(
          state,
          "cross_encoder_rerank",
          event,
          reranked ? "ok" : "skipped",
          reranked ? "reranked" : "idle (unused)",
          reranked ? "ON" : "idle",
        );
      }
      break;
    case "apply_retrieval_gate":
      writeNode(state, "apply_retrieval_gate", event, event.status, event.summary, metric);
      if (event.status === "refused") {
        writeNode(state, "refuse_if_weak", event, "refused", event.summary, "REFUSE");
      }
      break;
    case "rewrite_query":
      writeNode(state, "rewrite_query", event, event.status, event.summary, metric);
      if (event.status === "skipped") {
        writeNode(state, "retrieve_again", event, "skipped", "skipped", "skip");
      }
      break;
    case "build_context":
      writeNode(state, "build_context", event, event.status, event.summary, metric);
      break;
    case "generate_answer":
      writeNode(state, "generate_answer", event, event.status, event.summary, metric);
      if (event.status === "ok") {
        writeNode(state, "citations", event, "ok", "timestamped proofs", "OK");
        writeNode(state, "refuse_if_weak", event, "skipped", "not needed", "skip");
      } else if (event.status === "refused") {
        writeNode(state, "citations", event, "skipped", "no proofs", "skip");
        writeNode(state, "refuse_if_weak", event, "refused", event.summary, "REFUSE");
      } else if (event.status === "skipped") {
        writeNode(state, "citations", event, "skipped", "skipped", "skip");
      }
      break;
    case "pipeline":
      writeNode(state, "refuse_if_weak", event, "failed", event.summary, "FAIL");
      break;
    default:
      break;
  }
}

function embedStatus(status: PipelineEventStatus): PipelineEventStatus {
  if (status === "retry") return "ok";
  return status;
}

function writeNode(
  state: Record<DisplayNodeId, NodeRuntimeState>,
  id: DisplayNodeId,
  event: PipelineEvent,
  status: NodeRuntimeStatus,
  summary: string,
  metric: string,
) {
  const current = state[id];
  if (current.status === "refused" && status === "skipped") return;
  state[id] = {
    status,
    durationMs: event.duration_ms,
    summary,
    metric,
    event,
  };
}

export function metricFor(event: PipelineEvent): string {
  const payload = event.payload;
  const score = scoreFromPayload(payload);
  if (typeof payload.hit_count === "number") {
    return score ? `${payload.hit_count} · ${score}` : `${payload.hit_count} hits`;
  }
  if (typeof payload.fused_count === "number") {
    return score ? `${payload.fused_count} · ${score}` : `${payload.fused_count} fused`;
  }
  if (typeof payload.intent === "string") return payload.intent;
  if (payload.passed === true) return score ? `PASS · ${score}` : "PASS";
  if (payload.passed === false) return "REFUSE";
  if (event.status === "skipped") return "skip";
  if (event.status === "retry") return "RETRY";
  if (event.status === "failed") return "FAIL";
  if (event.status === "refused") return "REFUSE";
  if (score) return score;
  if (typeof event.duration_ms === "number" && event.duration_ms > 0) {
    return `${Math.round(event.duration_ms)}ms`;
  }
  return "";
}

/** Best display score from a pipeline event payload (retrieval, gate, or answer). */
export function scoreFromPayload(payload: Record<string, unknown>): string | null {
  const top = asNum(payload.top_score);
  if (top != null) return top.toFixed(2);

  const transcript = asNum(payload.transcript_score);
  const visual = asNum(payload.visual_score);
  if (transcript != null && visual != null) {
    return `${transcript.toFixed(2)} / ${visual.toFixed(2)}`;
  }
  if (transcript != null) return transcript.toFixed(2);
  if (visual != null) return visual.toFixed(2);

  const confidence = asNum(payload.confidence);
  if (confidence != null) return confidence.toFixed(2);

  const hitScores = asHits(payload)
    .map((hit) => asNum(hit.score))
    .filter((value): value is number => value != null);
  if (hitScores.length) return Math.max(...hitScores).toFixed(2);

  return null;
}

export function asNum(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

const EVENT_TO_DISPLAY: Partial<Record<string, DisplayNodeId>> = {
  validate_query: "validate_query",
  classify_intent: "classify_intent",
  retrieve_transcript: "retrieve_transcript",
  retrieve_visual: "retrieve_visual",
  fuse_results: "rrf_fuse",
  apply_retrieval_gate: "apply_retrieval_gate",
  rewrite_query: "rewrite_query",
  build_context: "build_context",
  generate_answer: "generate_answer",
  pipeline: "refuse_if_weak",
};

export function displayNodeForEvent(
  event: PipelineEvent,
  nodes: Record<DisplayNodeId, NodeRuntimeState>,
): DisplayNodeId | null {
  const mapped = EVENT_TO_DISPLAY[event.node];
  if (mapped && nodes[mapped].event?.ts === event.ts) return mapped;
  return (
    ALL_DISPLAY_NODES.find((id) => {
      const bound = nodes[id].event;
      return bound?.node === event.node && bound.ts === event.ts;
    }) ?? null
  );
}

export function healthCounts(nodes: Record<DisplayNodeId, NodeRuntimeState>) {
  const counts = { ok: 0, skipped: 0, refused: 0, active: 0 };
  for (const node of Object.values(nodes)) {
    if (node.status === "ok" || node.status === "retry") counts.ok += 1;
    else if (node.status === "skipped") counts.skipped += 1;
    else if (node.status === "refused" || node.status === "failed") counts.refused += 1;
    else if (node.status === "started") counts.active += 1;
  }
  return counts;
}

export function isRetryLive(nodes: Record<DisplayNodeId, NodeRuntimeState>): boolean {
  const rewrite = nodes.rewrite_query.status;
  const again = nodes.retrieve_again.status;
  return (
    rewrite === "started" ||
    rewrite === "ok" ||
    rewrite === "failed" ||
    rewrite === "retry" ||
    again === "started" ||
    again === "ok" ||
    again === "retry"
  );
}

export function asHits(payload: Record<string, unknown>): PipelineHitSnippet[] {
  const hits = payload.hits;
  if (!Array.isArray(hits)) return [];
  return hits.filter(isHit);
}

function isHit(value: unknown): value is PipelineHitSnippet {
  if (!value || typeof value !== "object") return false;
  const hit = value as PipelineHitSnippet;
  return typeof hit.video_id === "string" && typeof hit.snippet === "string";
}

export function formatClock(ts: string): string {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return ts.slice(11, 23) || ts;
  return date.toLocaleTimeString("en-GB", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function nodeLabel(id: DisplayNodeId): string {
  for (const column of PIPELINE_COLUMNS) {
    const node = column.nodes.find((item) => item.id === id);
    if (node) return node.label;
  }
  return id;
}

export const ALL_DISPLAY_NODES = PIPELINE_COLUMNS.flatMap((column) =>
  column.nodes.map((node) => node.id),
);
