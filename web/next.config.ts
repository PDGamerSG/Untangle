import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  async rewrites() {
    const api = (process.env.UNTANGLE_API_URL ?? "http://127.0.0.1:8090").replace(/\/+$/, "");
    return {
      beforeFiles: [
        { source: "/", destination: "/welcome/index.html" },
        { source: "/api/:path*", destination: `${api}/:path*` },
      ],
      afterFiles: [],
      fallback: [],
    };
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
