import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  images: {
    unoptimized: true,
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
          { key: "X-Frame-Options", value: "" },
        ],
      },
    ];
  },
};

export default nextConfig;
