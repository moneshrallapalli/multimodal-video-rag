/** Typed client for the FastAPI backend. Base URL is configurable for deployment. */
import type {
  DemoVideo,
  IngestRequest,
  IngestResponse,
  JobsResponse,
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

export const api = {
  // public
  videos: () => http<DemoVideo[]>("/api/videos"),
  search: (body: SearchRequest) =>
    http<SearchResponse>("/api/search", { method: "POST", body: JSON.stringify(body) }),
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
