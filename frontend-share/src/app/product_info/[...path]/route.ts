import { proxyProductInfoRequest } from '@/lib/proxy-product-info';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 300;

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

const handle = async (request: Request, context: RouteContext) => {
  const { path } = await context.params;
  return proxyProductInfoRequest(request, path);
};

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
