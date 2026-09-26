import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces a self-contained server for the Docker image (`.next/standalone`).
  output: "standalone",
};

export default nextConfig;
