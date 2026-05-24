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

export default nextConfig;
