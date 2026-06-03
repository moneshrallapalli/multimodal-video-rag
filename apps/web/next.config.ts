import type { NextConfig } from "next";

// Keep browser calls same-origin and let Next proxy /api/* to the backend. In
// production this avoids cross-site admin cookies; set API_PROXY_TARGET in Vercel.
const API_PROXY_TARGET = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [{ protocol: "https", hostname: "i.ytimg.com" }],
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_PROXY_TARGET}/api/:path*` },
      { source: "/health", destination: `${API_PROXY_TARGET}/health` },
    ];
  },
};

export default nextConfig;
