import { getApiUpstreamUrl } from '@/lib/api-upstream';
import { fetchWithReport } from '@/lib/fetch-with-report';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** SSE 流式代理：Next.js rewrite 会缓冲响应，导致前端看不到逐条 log。 */
export const POST = async (request: Request) => {
  const upstream = getApiUpstreamUrl();
  const body = await request.text();

  const upstreamResponse = await fetchWithReport(
    `${upstream}/dialog/generate`,
    {
      method: 'POST',
      headers: {
        'Content-Type':
          request.headers.get('content-type') ?? 'application/json',
        Accept: request.headers.get('accept') ?? 'text/event-stream',
      },
      body,
      ignoreClientErrors: true,
    },
  );

  if (!upstreamResponse.body) {
    return new Response(await upstreamResponse.text(), {
      status: upstreamResponse.status,
      headers: {
        'Content-Type': upstreamResponse.headers.get('content-type') ?? 'text/plain',
      },
    });
  }

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
};
