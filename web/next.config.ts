import type { NextConfig } from "next";

// The browser only ever talks to this app's own origin; /api is proxied to the backend, so the backend needs no CORS
// and session cookies stay first-party (SameSite=Strict).
const API_URL = process.env.API_URL ?? "http://localhost:8000";
const isDev = process.env.NODE_ENV !== "production";
// The admin console (served from this app under /admin) uploads CSV files through the /api proxy, and Next drops any proxied
// request body over 10 MB by default. The proxy buffers the body in memory, so a small server should build with a lower limit
// (PROXY_BODY_LIMIT=40mb) and load big files with the command line instead; the API enforces MAX_UPLOAD_MB either way.
const PROXY_BODY_LIMIT = (process.env.PROXY_BODY_LIMIT ?? "520mb") as NonNullable<NextConfig["experimental"]>["proxyClientMaxBodySize"];

const csp = [
  "default-src 'self'",
  // Next.js injects small inline bootstrap scripts; dev tooling additionally needs eval.
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self'${isDev ? " ws:" : ""}`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  experimental: { proxyClientMaxBodySize: PROXY_BODY_LIMIT },
  agentRules: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          ...(isDev ? [] : [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" }]),
        ],
      },
    ];
  },
};

export default nextConfig;
