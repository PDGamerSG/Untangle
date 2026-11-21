import type { NextConfig } from "next";

const dev = process.env.NODE_ENV !== "production";

// Next.js inlines its hydration payload in <script> tags, so scripts need 'unsafe-inline' unless every page is
// rendered per request with a nonce. Everything else is limited to this origin; nothing loads from third parties.
const appPolicy = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self'${dev ? " ws: http://127.0.0.1:* http://localhost:*" : ""}`,
  "media-src 'self' blob:",
  "worker-src 'self' blob:",
  "manifest-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  ...(dev ? [] : ["upgrade-insecure-requests"]),
].join("; ");

// The static landing page has no inline scripts; its inline style attributes position the animated labels.
const landingPolicy = appPolicy.replace(`script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`, "script-src 'self'");

const shared = [
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  { key: "X-DNS-Prefetch-Control", value: "off" },
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [
      { source: "/:path*", headers: [...shared, { key: "Content-Security-Policy", value: appPolicy }] },
      // Later entries override earlier ones for the same header.
      { source: "/", headers: [{ key: "Content-Security-Policy", value: landingPolicy }] },
      { source: "/welcome/:path*", headers: [{ key: "Content-Security-Policy", value: landingPolicy }] },
    ];
  },
  cacheComponents: true,
  partialPrefetching: true,
  async rewrites() {
    const api = (process.env.UNTANGLE_API_URL ?? "http://127.0.0.1:8090").replace(/\/+$/, "");
    return {
      beforeFiles: [
        { source: "/", destination: "/welcome/index.html" },
        // Vercel routes /api directly to the Python service in this same deployment.
        // Local Next.js still proxies to `untangle serve` (or UNTANGLE_API_URL).
        ...(process.env.VERCEL === "1" ? [] : [{ source: "/api/:path*", destination: `${api}/:path*` }]),
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
