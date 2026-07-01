import { withSentryConfig } from '@sentry/nextjs';

/** @type {import('next').NextConfig} */
const isProductionBuild = process.env.NODE_ENV === 'production';

const apiUpstream =
  process.env.API_UPSTREAM_URL ??
  (isProductionBuild ? 'http://backend:8000' : 'http://localhost:8000');

const nextConfig = {
  output: 'standalone',
  reactCompiler: true,
  async rewrites() {
    return [
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
        source: '/shares',
        destination: `${apiUpstream}/shares`,
      },
      {
        source: '/shares/:path*',
        destination: `${apiUpstream}/shares/:path*`,
      },
      {
        source: '/social/:path*',
        destination: `${apiUpstream}/social/:path*`,
      },
      {
        source: '/lark/:path*',
        destination: `${apiUpstream}/lark/:path*`,
      },
    ];
  },
};

// Better Stack source map upload (Sentry-compatible plugin).
// Requires SENTRY_ORG, SENTRY_PROJECT (or SENTRY_APPLICATION_ID), SENTRY_URL, SENTRY_AUTH_TOKEN.
// See https://betterstack.com/docs/errors/collecting-errors/upload-source-maps/
const sentrySourcemapsEnabled = Boolean(
  process.env.SENTRY_AUTH_TOKEN &&
    process.env.SENTRY_ORG &&
    process.env.SENTRY_URL &&
    (process.env.SENTRY_PROJECT || process.env.SENTRY_APPLICATION_ID),
);

export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT ?? process.env.SENTRY_APPLICATION_ID,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  sentryUrl: process.env.SENTRY_URL,
  silent: !process.env.CI,
  widenClientFileUpload: true,
  sourcemaps: {
    disable: !sentrySourcemapsEnabled,
  },
});
