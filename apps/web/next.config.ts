import type { NextConfig } from "next";

// Dev/preview: the browser calls the API same-origin and Next proxies to the backend
// (no CORS, works from sandboxed browsers). Production: set NEXT_PUBLIC_API_BASE_URL to
// the API Gateway URL so the browser calls it directly (CORS is configured on the API).
const API_PROXY_TARGET = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    if (process.env.NEXT_PUBLIC_API_BASE_URL) return [];
    return [
      { source: "/api/:path*", destination: `${API_PROXY_TARGET}/api/:path*` },
      { source: "/health", destination: `${API_PROXY_TARGET}/health` },
    ];
  },
};

export default nextConfig;
