/**
 * TypeScript mirror of the Pydantic contracts in `packages/shared/src/shared/schemas.py`.
 * Keep these in sync by hand; OpenAPI→TS codegen is a later improvement.
 */
export type Modality = "visual" | "transcript" | "visual_caption";
export type QueryIntent =
  | "visual"
  | "transcript"
  | "hybrid"
  | "timestamp"
  | "summary"
  | "no_answer";
export type JobStatus =
  | "queued"
  | "downloading"
  | "transcribing"
  | "embedding"
  | "completed"
  | "failed";
export type IngestStage =
  | "queued"
  | "fetch_metadata"
  | "download_video"
  | "extract_audio"
  | "extract_frames"
  | "caption_frames"
  | "transcribe"
  | "embed_upsert"
  | "refresh_bm25"
  | "write_catalog"
  | "completed";

export interface VideoArtifactStats {
  transcript_segments: number | null;
  transcript_chunks: number | null;
  visual_frames: number | null;
  indexed_vectors: number | null;
  frame_interval_seconds: number | null;
}

export interface DemoVideo {
  id: string;
  title: string;
  author: string;
  domain: string | null;
  thumbnail_url: string;
  youtube_url: string;
  duration_seconds: number | null;
  indexed: boolean;
  artifact_stats: VideoArtifactStats | null;
}

export interface SearchRequest {
  query: string;
  video_ids?: string[] | null;
  top_k?: number;
}

export interface SearchResult {
  rank: number;
  video_id: string;
  title: string;
  start_seconds: number;
  end_seconds: number;
  modality: Modality;
  score: number;
  snippet: string;
  thumbnail_url: string;
  seek_url: string;
}

export interface SearchResponse {
  query: string;
  rewritten_query: string | null;
  intent: QueryIntent;
  answer: string | null;
  refused: boolean;
  refusal_reason?: string | null;
  confidence: number;
  results: SearchResult[];
}

export type PipelineEventStatus =
  | "started"
  | "ok"
  | "skipped"
  | "retry"
  | "failed"
  | "refused";

export interface PipelineHitSnippet {
  video_id: string;
  start_seconds: number;
  snippet: string;
  score?: number | null;
  modality?: string | null;
}

export interface PipelineEvent {
  run_id: string;
  ts: string;
  node: string;
  status: PipelineEventStatus;
  duration_ms: number | null;
  summary: string;
  payload: Record<string, unknown>;
}

export interface IngestRequest {
  youtube_url: string;
  frame_interval_seconds?: number | null;
  max_frames?: number | null;
}

export interface Job {
  id: string;
  youtube_url: string;
  video_id: string | null;
  title: string | null;
  status: JobStatus;
  progress: number;
  created_at: string;
  updated_at: string;
  error: string | null;
  stage?: IngestStage | null;
  stages_seen?: string[];
}

export interface JobsResponse {
  jobs: Job[];
}

export interface IngestResponse {
  job: Job;
}

export interface SessionStatus {
  authenticated: boolean;
}
