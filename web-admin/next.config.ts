import type { NextConfig } from "next";

// The browser only ever talks to this app's own origin; /api is proxied to the backend, so the backend needs no CORS
// and session cookies stay first-party (SameSite=Strict). This standalone console has no operator MFA yet, so keep
// it off the public internet: bind it to localhost only and reach it over a VPN or SSH tunnel.
const API_URL = process.env.API_URL ?? "http://localhost:8000";
const isDev = process.env.NODE_ENV !== "production";

const csp = [
  "default-src 'self'",
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
  // CSV imports are large. Next's proxy drops any request body over 10 MB by default, which broke uploads of
  // customers/sales files; allow up to the API's own 500 MB limit (plus multipart overhead).
  experimental: { proxyClientMaxBodySize: "520mb" },
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
