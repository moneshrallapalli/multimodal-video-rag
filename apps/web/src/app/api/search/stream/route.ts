import { NextRequest } from "next/server";

const API_PROXY_TARGET = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";

/** Same-origin SSE proxy so the homepage can watch node events without
 * the Next rewrite layer buffering the FastAPI stream. */
export async function POST(request: NextRequest) {
  const upstream = await fetch(`${API_PROXY_TARGET}/api/search/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: await request.text(),
    cache: "no-store",
  });

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
