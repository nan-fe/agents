import { getApiUpstreamUrl } from '@/lib/api-upstream';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const UPSTREAM_TIMEOUT_MS = 10 * 60 * 1000;

/** SSE 流式代理：rewrite 会缓冲响应，必须由 Route Handler 转发到后端。 */
export const POST = async (request: Request) => {
  const upstream = getApiUpstreamUrl();
  const body = await request.text();

  const timeoutController = new AbortController();
  const timeoutId = setTimeout(() => timeoutController.abort(), UPSTREAM_TIMEOUT_MS);
  const abortSignals = [timeoutController.signal];
  if (request.signal) {
    abortSignals.push(request.signal);
  }
  const signal = AbortSignal.any(abortSignals);

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(`${upstream}/social-hotspots/analyze/stream`, {
      method: 'POST',
      headers: {
        'Content-Type':
          request.headers.get('content-type') ?? 'application/json',
        Accept: request.headers.get('accept') ?? 'text/event-stream',
      },
      body,
      signal,
      cache: 'no-store',
    });
  } catch (error) {
    const message =
      error instanceof Error && error.name === 'AbortError'
        ? '热点分析已取消或上游超时'
        : '热点分析上游连接失败';
    return new Response(message, { status: 504 });
  } finally {
    clearTimeout(timeoutId);
  }

  if (!upstreamResponse.ok) {
    return new Response(await upstreamResponse.text(), {
      status: upstreamResponse.status,
      headers: {
        'Content-Type': upstreamResponse.headers.get('content-type') ?? 'text/plain',
      },
    });
  }

  if (!upstreamResponse.body) {
    return new Response('上游未返回流式响应', { status: 502 });
  }

  const reader = upstreamResponse.body.getReader();

  const stream = new ReadableStream({
    async pull(controller) {
      const { done, value } = await reader.read();
      if (done) {
        controller.close();
        return;
      }
      controller.enqueue(value);
    },
    cancel() {
      void reader.cancel();
    },
  });

  return new Response(stream, {
    status: upstreamResponse.status,
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
};
