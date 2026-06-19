import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "cdn.nba.com",
        pathname: "/logos/nba/**",
      },
    ],
  },
  async headers() {
    return [
      {
        source: "/card",
        headers: [
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors 'self' https://gerritvisser.de https://*.gerritvisser.de",
          },
          // Remove Next.js default SAMEORIGIN so the iframe works cross-subdomain
          { key: "X-Frame-Options", value: "" },
        ],
      },
    ];
  },
};

export default nextConfig;
