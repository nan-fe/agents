/** @type {import('next').NextConfig} */
const studioUpstream =
  process.env.STUDIO_UPSTREAM_URL ?? 'http://localhost:5173';
const apiUpstream = process.env.API_UPSTREAM_URL ?? 'http://localhost:8000';

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
      {
        source: '/dialog/:path*',
        destination: `${apiUpstream}/dialog/:path*`,
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

export default nextConfig;
