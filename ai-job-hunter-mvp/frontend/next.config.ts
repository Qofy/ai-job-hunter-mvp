import type { NextConfig } from "next";
const config: NextConfig = {
  // Use a separate directory for parallel preview processes to keep builds isolated.
  distDir: process.env.JOBPILOT_DIST_DIR || ".next",
  async rewrites() {
    const backend = (
      process.env.BACKEND_API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://127.0.0.1:8000"
    ).replace(/\/$/, "");
    return [
      { source: "/api/backend/:path*", destination: `${backend}/:path*` },
    ];
  },
};
export default config;
