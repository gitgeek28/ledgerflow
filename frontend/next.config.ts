import type { NextConfig } from "next";

// The browser only ever talks to this Next.js origin; /api/* is proxied to the FastAPI backend.
// Same-origin keeps the session cookie first-party and avoids CORS in the browser.
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
