import { getApiUpstreamUrl } from '@/lib/api-upstream';
import { fetchWithReport } from '@/lib/fetch-with-report';

/** Playwright 抓取 + LLM 解析可能超过 2 分钟 */
const PRODUCT_INFO_TIMEOUT_MS = 5 * 60 * 1000;

const buildUpstreamUrl = (pathSegments: string[], search: string) => {
  const upstream = getApiUpstreamUrl();
  const suffix = pathSegments.length > 0 ? `/${pathSegments.join('/')}` : '';
  return `${upstream}/product_info${suffix}${search}`;
};

const forwardHeaders = (request: Request): HeadersInit => {
  const headers: Record<string, string> = {
    Accept: request.headers.get('accept') ?? '*/*',
  };
  const contentType = request.headers.get('content-type');
  if (contentType) {
    headers['Content-Type'] = contentType;
  }
  return headers;
};

export const proxyProductInfoRequest = async (
  request: Request,
  pathSegments: string[],
): Promise<Response> => {
  const upstreamUrl = new URL(
    buildUpstreamUrl(pathSegments, new URL(request.url).search),
  );
  const method = request.method.toUpperCase();
  const hasBody = method !== 'GET' && method !== 'HEAD';
  const body = hasBody ? await request.text() : undefined;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), PRODUCT_INFO_TIMEOUT_MS);

  try {
    const upstreamResponse = await fetchWithReport(upstreamUrl, {
      method,
      headers: forwardHeaders(request),
      body,
      signal: controller.signal,
      ignoreClientErrors: true,
    });

    const responseBody = await upstreamResponse.text();
    return new Response(responseBody, {
      status: upstreamResponse.status,
      headers: {
        'Content-Type':
          upstreamResponse.headers.get('content-type') ?? 'application/json',
      },
    });
  } catch (error) {
    const isTimeout = error instanceof Error && error.name === 'AbortError';
    return new Response(
      JSON.stringify({
        detail: isTimeout
          ? '商品识别超时，请稍后重试'
          : '商品服务暂时不可用，请稍后重试',
      }),
      {
        status: isTimeout ? 504 : 502,
        headers: { 'Content-Type': 'application/json' },
      },
    );
  } finally {
    clearTimeout(timeout);
  }
};
