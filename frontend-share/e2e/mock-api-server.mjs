/**
 * Lightweight mock backend for Playwright E2E (port 8000 by default).
 * Handles dialog SSE, projects, shares, and product_info without real LLM/scraper.
 */
import http from 'node:http';
import { randomBytes } from 'node:crypto';

const PORT = Number(process.env.MOCK_API_PORT ?? process.env.PORT ?? 8000);

const seedProduct = () => ({
  id: 'prod-e2e-1',
  name: 'E2E 测试蓝牙耳机',
  category: '数码',
  price: 199,
  description: '用于 E2E 测试的商品描述。',
  sales: 1200,
  shop_name: 'E2E 测试店',
  url: 'https://item.jd.com/123456.html',
  cover_image: null,
  comments: [],
});

const state = {
  projectCounter: 0,
  products: [seedProduct()],
  shares: new Map(),
  previews: new Map(),
  dialogGenerateCalls: [],
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const json = (res, status, body) => {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(body));
};

const readBody = (req) =>
  new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (chunk) => {
      data += chunk;
    });
    req.on('end', () => {
      if (!data) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(data));
      } catch (error) {
        reject(error);
      }
    });
    req.on('error', reject);
  });

const newShareId = () => randomBytes(6).toString('base64url');

const handleProjects = (req, res, url) => {
  if (req.method === 'GET' && url.pathname === '/projects') {
    json(res, 200, { projects: [] });
    return true;
  }

  if (req.method === 'POST' && url.pathname === '/projects') {
    state.projectCounter += 1;
    json(res, 200, { project_id: `proj-e2e-${state.projectCounter}` });
    return true;
  }

  if (req.method === 'POST' && url.pathname === '/projects/finalize') {
    json(res, 200, {
      project_id: 'proj-e2e-finalized',
      finalized: false,
      version_count: 0,
      message: '无版本记录，跳过汇总',
    });
    return true;
  }

  return false;
};

const handleShares = async (req, res, url) => {
  if (req.method === 'POST' && url.pathname === '/shares') {
    const body = await readBody(req);
    const shareId = newShareId();
    const createdAt = new Date().toISOString();
    const snapshot = {
      id: shareId,
      title: body.title ?? '',
      content: body.content ?? '',
      hashtags: Array.isArray(body.hashtags) ? body.hashtags : [],
      image_url: body.image_url ?? null,
      message: body.message ?? null,
      created_at: createdAt,
      expires_at: null,
    };
    state.shares.set(shareId, snapshot);
    json(res, 200, { share_id: shareId, share: snapshot });
    return true;
  }

  const shareMatch = url.pathname.match(/^\/shares\/([^/]+)$/);
  if (req.method === 'GET' && shareMatch) {
    const snapshot = state.shares.get(decodeURIComponent(shareMatch[1]));
    if (!snapshot) {
      json(res, 404, { detail: '分享不存在' });
      return true;
    }
    json(res, 200, snapshot);
    return true;
  }

  return false;
};

const handleProductInfo = async (req, res, url) => {
  if (req.method === 'GET' && url.pathname === '/product_info/list') {
    json(res, 200, { items: state.products, total: state.products.length });
    return true;
  }

  if (req.method === 'POST' && url.pathname === '/product_info/preview') {
    const body = await readBody(req);
    const previewToken = `preview-${randomBytes(4).toString('hex')}`;
    const product = {
      ...seedProduct(),
      id: 'prod-preview',
      name: 'E2E 预览商品',
      url: body.url ?? seedProduct().url,
    };
    state.previews.set(previewToken, product);
    json(res, 200, {
      preview_token: previewToken,
      product,
      message: '识别完成',
    });
    return true;
  }

  if (req.method === 'POST' && url.pathname === '/product_info/confirm') {
    const body = await readBody(req);
    const preview = state.previews.get(body.preview_token);
    if (!preview) {
      json(res, 400, { detail: '预览已过期' });
      return true;
    }
    const product = { ...preview, id: `prod-e2e-${state.products.length + 1}` };
    state.products.push(product);
    state.previews.delete(body.preview_token);
    json(res, 200, { product, message: '商品已加入选品池' });
    return true;
  }

  const detailMatch = url.pathname.match(/^\/product_info\/([^/]+)$/);
  if (detailMatch) {
    const productId = decodeURIComponent(detailMatch[1]);
    if (req.method === 'GET') {
      const product = state.products.find((item) => item.id === productId);
      if (!product) {
        json(res, 404, { detail: '商品不存在' });
        return true;
      }
      json(res, 200, product);
      return true;
    }
    if (req.method === 'DELETE') {
      const before = state.products.length;
      state.products = state.products.filter((item) => item.id !== productId);
      if (state.products.length === before) {
        json(res, 404, { detail: '商品不存在' });
        return true;
      }
      json(res, 200, { ok: true });
      return true;
    }
  }

  return false;
};

const handleDialogGenerate = async (req, res, body) => {
  state.dialogGenerateCalls.push(body);

  res.writeHead(200, {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
  });

  const projectId = body.project_id ?? `proj-e2e-${state.projectCounter || 1}`;
  const events = [
    {
      id: '1',
      data: {
        type: 'log',
        data: {
          from: '编排',
          message: '正在分析需求…',
          timestamp: new Date().toISOString(),
        },
      },
    },
    {
      id: '2',
      data: {
        type: 'log',
        data: {
          from: '文案',
          message: '正在撰写正文…',
          timestamp: new Date().toISOString(),
        },
      },
    },
    {
      id: '3',
      data: {
        type: 'result',
        data: {
          title: 'E2E 测试种草标题',
          content:
            '这是一段 E2E 模拟生成的正文，用于验证流式对话与分享链路。',
          hashtags: ['E2E测试', '好物分享'],
          image_url: '',
          project_id: projectId,
        },
      },
    },
  ];

  for (const event of events) {
    await sleep(120);
    res.write(`id: ${event.id}\n`);
    res.write(`data: ${JSON.stringify(event.data)}\n\n`);
  }

  res.end();
};

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url ?? '/', `http://127.0.0.1:${PORT}`);

  if (req.method === 'GET' && url.pathname === '/health') {
    json(res, 200, { ok: true, dialog_calls: state.dialogGenerateCalls.length });
    return;
  }

  if (req.method === 'GET' && url.pathname === '/e2e/reset') {
    state.projectCounter = 0;
    state.products = [seedProduct()];
    state.shares.clear();
    state.previews.clear();
    state.dialogGenerateCalls = [];
    json(res, 200, { ok: true });
    return;
  }

  try {
    if (handleProjects(req, res, url)) {
      return;
    }
    if (await handleShares(req, res, url)) {
      return;
    }
    if (await handleProductInfo(req, res, url)) {
      return;
    }

    if (req.method === 'POST' && url.pathname === '/dialog/generate') {
      const body = await readBody(req);
      await handleDialogGenerate(req, res, body);
      return;
    }
  } catch (error) {
    console.error('[mock-api]', error);
    json(res, 500, { detail: 'mock server error' });
    return;
  }

  json(res, 404, { detail: `mock route not found: ${req.method} ${url.pathname}` });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[mock-api] listening on http://127.0.0.1:${PORT}`);
});

const shutdown = () => {
  server.close(() => process.exit(0));
};

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
