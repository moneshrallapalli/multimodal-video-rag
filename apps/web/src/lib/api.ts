/** Typed client for the FastAPI backend. Base URL is configurable for deployment. */
import type {
  DemoVideo,
  IngestRequest,
  IngestResponse,
  JobsResponse,
  PipelineEvent,
  SearchRequest,
  SearchResponse,
  SessionStatus,
} from "./types";

// Empty = same-origin (Next proxies to the backend via next.config rewrites).
// Direct API URLs are supported for public-only previews, but production admin
// should stay same-origin so session cookies are first-party.
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    credentials: "include", // send the admin session cookie
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // non-JSON error body — keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

async function readSearchStream(
  body: SearchRequest,
  options: { onEvent: (event: PipelineEvent) => void; signal?: AbortSignal },
): Promise<SearchResponse> {
  const res = await fetch(`${BASE_URL}/api/search/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    credentials: "include",
    body: JSON.stringify(body),
    signal: options.signal,
  });
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      const json = await res.json();
      if (json?.detail) detail = json.detail;
    } catch {
      // keep statusText
    }
    throw new ApiError(res.status || 502, detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let final: SearchResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      buffer += decoder.decode();
      if (buffer.trim()) {
        const parsed = parseSseBlock(buffer);
        if (parsed?.event === "node") options.onEvent(parsed.data as PipelineEvent);
        if (parsed?.event === "final") final = parsed.data as SearchResponse;
      }
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const parsed = parseSseBlock(block);
      if (!parsed) continue;
      if (parsed.event === "node") {
        options.onEvent(parsed.data as PipelineEvent);
      } else if (parsed.event === "final") {
        final = parsed.data as SearchResponse;
      }
    }
  }

  if (!final) {
    throw new ApiError(502, "Search stream ended without a response");
  }
  return final;
}

function parseSseBlock(block: string): { event: string; data: unknown } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!dataLines.length) return null;
  const raw = dataLines.join("\n");
  if (!raw || raw === "{}") return { event, data: {} };
  return { event, data: JSON.parse(raw) };
}

export const api = {
  // public
  videos: () => http<DemoVideo[]>("/api/videos"),
  search: (body: SearchRequest) =>
    http<SearchResponse>("/api/search", { method: "POST", body: JSON.stringify(body) }),
  searchStream: (
    body: SearchRequest,
    options: { onEvent: (event: PipelineEvent) => void; signal?: AbortSignal },
  ) => readSearchStream(body, options),
  // admin
  login: (password: string) =>
    http<SessionStatus>("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
  logout: () => http<SessionStatus>("/api/admin/logout", { method: "POST" }),
  session: () => http<SessionStatus>("/api/admin/session"),
  jobs: () => http<JobsResponse>("/api/admin/jobs"),
  ingest: (body: IngestRequest) =>
    http<IngestResponse>("/api/admin/ingest", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
