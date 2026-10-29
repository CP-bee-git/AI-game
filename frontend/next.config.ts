import type { NextConfig } from "next";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = dirname(frontendDir);

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: repositoryRoot,
  turbopack: { root: repositoryRoot },
  experimental: { proxyTimeout: 300_000 },
  async rewrites() {
    const backend = (process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;

