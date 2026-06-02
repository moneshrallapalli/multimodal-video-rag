/**
 * TypeScript mirror of the Pydantic contracts in `packages/shared/src/shared/schemas.py`.
 * Keep these in sync by hand (Phase 1); OpenAPI→TS codegen is a later improvement.
 */
export type Modality = "visual" | "transcript";
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

export interface DemoVideo {
  id: string;
  title: string;
  author: string;
  thumbnail_url: string;
  youtube_url: string;
  duration_seconds: number | null;
}

export interface SearchRequest {
  query: string;
  video_id?: string | null;
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
  confidence: number;
  results: SearchResult[];
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
