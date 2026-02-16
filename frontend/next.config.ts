import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  // Disable the experimental React compiler to avoid requiring
  // additional build-time plugins until we intentionally opt-in.
  reactCompiler: false,
};

export default nextConfig;
