import { withSentryConfig } from '@sentry/nextjs';

/** @type {import('next').NextConfig} */
const isProductionBuild = process.env.NODE_ENV === 'production';

const studioUpstream =
  process.env.STUDIO_UPSTREAM_URL ??
  (isProductionBuild ? 'http://frontend:80' : 'http://localhost:5173');
const apiUpstream =
  process.env.API_UPSTREAM_URL ??
  (isProductionBuild ? 'http://backend:8000' : 'http://localhost:8000');

const nextConfig = {
  output: 'standalone',
  reactCompiler: true,
  async rewrites() {
    return [
      {
        source: '/studio',
        destination: `${studioUpstream}/studio/`,
      },
      {
        source: '/studio/:path*',
        destination: `${studioUpstream}/studio/:path*`,
      },
      // /dialog/generate 由 app/dialog/generate/route.ts 流式代理（rewrite 会缓冲 SSE）
      // /product_info/* 由 app/product_info/[...path]/route.ts 长超时代理（rewrite 约 30s 超时）
      {
        source: '/projects',
        destination: `${apiUpstream}/projects`,
      },
      {
        source: '/projects/:path*',
        destination: `${apiUpstream}/projects/:path*`,
      },
      {
        source: '/session/:path*',
        destination: `${apiUpstream}/session/:path*`,
      },
      {
        source: '/shares/:path*',
        destination: `${apiUpstream}/shares/:path*`,
      },
    ];
  },
};

export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG ?? 'better-stack',
  project: process.env.SENTRY_APPLICATION_ID ?? 'frontend-share',
  silent: !process.env.CI,
  // Better Stack 通过 DSN 接入，无需 Sentry.io source map 上传
  sourcemaps: {
    disable: true,
  },
});
