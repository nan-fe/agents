/**
 * API服务 - 封装SSE连接
 */

import type { components } from "../api/schema.d.ts";
import { parseSSEStream } from "../lib/sse/sse-parser";
import type { StreamIngestor } from "../lib/sse/sse-stream-ingest";

/**
 * 上报已捕获错误到 Better Stack，附上操作名和可选上下文。
 * 在 try/catch 中用于不应静默吞掉的接口/业务错误。
 */
export const reportError = async (
  error: unknown,
  operation: string,
  extra?: Record<string, unknown>,
): Promise<void> => {
  if (typeof window === 'undefined') return;
  const Sentry = await import('@sentry/nextjs');
  Sentry.captureException(error, {
    tags: { operation },
    extra,
  });
};


/** Browser: same-origin (Next rewrites / route handlers). SSR/server: upstream. */
export const API_BASE_URL =
  typeof window !== "undefined"
    ? ""
    : (process.env.API_BASE_URL ??
      process.env.API_UPSTREAM_URL ??
      "http://localhost:8000");

const getShareBaseUrl = () => {

  if (typeof window === "undefined") {
    return "";
  }

  return window.location.origin;
};

export const SHARE_BASE_URL = getShareBaseUrl();

export type UserInput = components["schemas"]["UserInput"];
export type ProjectFinalizeRequest = components["schemas"]["ProjectFinalizeRequest"];
export type ProjectFinalizeResponse = components["schemas"]["ProjectFinalizeResponse"];
export type ProjectCreateResponse = components["schemas"]["ProjectCreateResponse"];
export type ProjectConversationResponse =
  components["schemas"]["ProjectConversationResponse"];
export type ProjectListResponse = components["schemas"]["ProjectListResponse"];
export type ProjectListItem = components["schemas"]["ProjectListItem"];

export type ShareResult = {
  title?: string;
  content?: string;
  hashtags?: string[];
  image_url?: string;
  message?: string;
  review_approved?: boolean;
  version_id?: string;
  weibo_publish?: {
    auto_started?: boolean;
    job_id?: string | null;
    share_id?: string | null;
    error?: string | null;
  };
};

export type ShareCreateResponse = {
  share_id: string;
  share: ShareResult & {
    id: string;
    created_at: string;
    expires_at?: string | null;
  };
};

export type ProductComment = {
  content: string;
  nickname?: string;
  score?: string;
  creation_time?: string;
};

export type ProductItem = {
  id: string;
  name: string;
  category: string;
  price: number;
  description: string;
  sales: number;
  shop_name: string;
  url?: string | null;
  cover_image?: string | null;
  comments?: ProductComment[];
};

export type ProductListResponse = {
  items: ProductItem[];
  total: number;
};

export type ProductInfoCreateResponse = {
  product: ProductItem;
  message: string;
};

export type ProductInfoPreviewResponse = {
  preview_token: string;
  product: ProductItem;
  message: string;
};

const parseApiError = async (response: Response): Promise<never> => {
  let detail = `HTTP error! status: ${response.status}`;
  try {
    const body = (await response.json()) as {
      detail?: string | Array<{ msg?: string }>;
    };
    if (typeof body.detail === "string") {
      detail = body.detail;
    } else if (Array.isArray(body.detail) && body.detail.length > 0) {
      detail = body.detail
        .map((item) => item.msg)
        .filter(Boolean)
        .join("；");
    }
  } catch {
    // ignore JSON parse errors
  }
  throw new Error(detail);
};

export const listProducts = async (): Promise<ProductListResponse> => {
  const response = await fetch(`${API_BASE_URL}/product_info/list`);
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const getProductDetail = async (productId: string): Promise<ProductItem> => {
  const response = await fetch(
    `${API_BASE_URL}/product_info/${encodeURIComponent(productId)}`,
  );

  if (!response.ok) {
    await parseApiError(response);
  }

  return response.json();
};

export const previewProductFromUrl = async (
  url: string,
): Promise<ProductInfoPreviewResponse> => {
  const response = await fetch(`${API_BASE_URL}/product_info/preview`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    await parseApiError(response);
  }

  return response.json();
};

export const confirmProductPreview = async (
  previewToken: string,
): Promise<ProductInfoCreateResponse> => {
  const response = await fetch(`${API_BASE_URL}/product_info/confirm`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ preview_token: previewToken }),
  });

  if (!response.ok) {
    await parseApiError(response);
  }

  return response.json();
};

export const deleteProduct = async (productId: string): Promise<void> => {
  const response = await fetch(
    `${API_BASE_URL}/product_info/${encodeURIComponent(productId)}`,
    { method: "DELETE" },
  );

  if (!response.ok) {
    await parseApiError(response);
  }
};

export const deleteProject = async (
  projectId: string,
  userId: string,
): Promise<void> => {
  const query = `?user_id=${encodeURIComponent(userId)}`;
  const response = await fetch(
    `${API_BASE_URL}/projects/${encodeURIComponent(projectId)}${query}`,
    { method: "DELETE" },
  );

  if (!response.ok) {
    await parseApiError(response);
  }
};

export type DialogSSEType = {
  request: UserInput;
  log_callback: (from: string, message: string) => void;
  streamIngestor?: StreamIngestor;
};

export const createProject = async (
  userId: string,
): Promise<ProjectCreateResponse> => {
  const response = await fetch(`${API_BASE_URL}/projects`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ user_id: userId }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
};

export const getProjects = async (
  userId: string,
): Promise<ProjectListResponse> => {
  const query = `?user_id=${encodeURIComponent(userId)}`;
  const response = await fetch(`${API_BASE_URL}/projects${query}`);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
};

export const getProjectConversation = async (
  projectId: string,
  userId: string,
): Promise<ProjectConversationResponse> => {
  const query = `?user_id=${encodeURIComponent(userId)}`;
  const response = await fetch(
    `${API_BASE_URL}/projects/${encodeURIComponent(projectId)}${query}`,
  );

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
};

export const finalizeProject = async (
  payload: ProjectFinalizeRequest,
): Promise<ProjectFinalizeResponse> => {
  const response = await fetch(`${API_BASE_URL}/projects/finalize`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    keepalive: true,
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
};

export const finalizeProjectBeacon = (payload: ProjectFinalizeRequest): void => {
  if (typeof navigator === "undefined" || !navigator.sendBeacon) {
    return;
  }

  const blob = new Blob([JSON.stringify(payload)], {
    type: "application/json",
  });
  navigator.sendBeacon(`${API_BASE_URL}/projects/finalize`, blob);
};

export const createDialogGenerateRequest = (
  request: UserInput,
  signal?: AbortSignal,
) => {
  return fetch(`${API_BASE_URL}/dialog/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(request),
    signal,
  });
};

export const generateDialogContent = async (
  param: DialogSSEType,
): Promise<any> => {
  const { request, log_callback, streamIngestor } = param;
  try {
    // 使用fetch API创建SSE连接
    const response = await createDialogGenerateRequest(request);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response?.body?.getReader();
    let finalResult: any = null;

    if (!reader) return null;

    await parseSSEStream({
      reader,
      parseMessage: (payload) => JSON.parse(payload),
      onMessage: (data: any, eventId) => {
        const enqueue = () => {
          if (data.type === "log") {
            log_callback?.(data.data.from, data.data.message);
          } else if (data.type === "meta") {
            // 展示名映射由后端在 log.from 中已解析；meta 供需要时扩展
          } else if (data.type === "result") {
            finalResult = data.data;
          }
        };

        if (streamIngestor) {
          streamIngestor.ingest(eventId, enqueue);
          return;
        }

        enqueue();
      },
      onParseError: (error) => {
        console.error("解析SSE消息失败:", error);
      },
    });

    return finalResult;
  } catch (error) {
    console.error("SSE连接错误:", error);
    await reportError(error, "generateDialogContent");
    throw error;
  }
};

export const buildShareUrl = (shareId: string): string => {
  const baseUrl = SHARE_BASE_URL.replace(/\/$/, "");
  return `${baseUrl}/share/${encodeURIComponent(shareId)}`;
};

export const createShare = async (
  result: ShareResult,
): Promise<ShareCreateResponse> => {
  const response = await fetch(`${API_BASE_URL}/shares`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      title: result.title ?? "",
      content: result.content ?? "",
      hashtags: Array.isArray(result.hashtags) ? result.hashtags : [],
      image_url: result.image_url ?? null,
      message: result.message ?? null,
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
};

export const rollbackToVersion = async (
  session_id: string,
  version: number,
): Promise<any> => {
  try {
    const response = await fetch(`${API_BASE_URL}/session/rollback`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ session_id, version }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error("回退版本失败:", error);
    await reportError(error, "rollbackToVersion", { session_id, version });
    throw error;
  }
};

export const compareVersions = async (
  session_id: string,
  version1: number,
  version2: number,
): Promise<any> => {
  try {
    const response = await fetch(`${API_BASE_URL}/session/compare`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ session_id, version1, version2 }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error("比较版本失败:", error);
    await reportError(error, "compareVersions", { session_id, version1, version2 });
    throw error;
  }
};

export type LarkStatusResponse = {
  auth: Record<string, unknown>;
  notify_chat_configured: boolean;
  notify_enabled: boolean;
  notify_mode: string;
};

export type LarkPushReviewPayload = {
  title?: string;
  content?: string;
  project_id?: string;
  version?: string;
  version_id?: string;
  image_url?: string;
  review_feedback?: string;
  hashtags?: string[];
  user_id?: string;
};

export type LarkOAuthUserStatus = {
  connected: boolean;
  user_id: string;
  expires_at?: string;
  has_refresh_token?: boolean;
  scope?: string;
};

export type LarkOAuthRegisterResponse = {
  client_id: string;
  client_secret: string;
  client_id_issued_at: number;
  redirect_uris: string[];
  scope: string;
};

export const registerLarkOAuthClient = async (
  clientName: string,
  redirectUris: string[],
): Promise<LarkOAuthRegisterResponse> => {
  const response = await fetch(`${API_BASE_URL}/lark/oauth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_name: clientName,
      redirect_uris: redirectUris,
    }),
  });
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const startLarkOAuthAuthorizeUrl = (params: {
  userId: string;
  returnUrl: string;
  clientId?: string;
}): string => {
  const query = new URLSearchParams({
    user_id: params.userId,
    return_url: params.returnUrl,
  });
  if (params.clientId) {
    query.set('client_id', params.clientId);
  }
  return `${API_BASE_URL}/lark/oauth/authorize?${query.toString()}`;
};

export const getLarkOAuthUserStatus = async (
  userId: string,
): Promise<LarkOAuthUserStatus> => {
  const response = await fetch(
    `${API_BASE_URL}/lark/oauth/user?user_id=${encodeURIComponent(userId)}`,
  );
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const disconnectLarkOAuth = async (userId: string): Promise<void> => {
  const response = await fetch(
    `${API_BASE_URL}/lark/oauth/user?user_id=${encodeURIComponent(userId)}`,
    { method: 'DELETE' },
  );
  if (!response.ok) {
    await parseApiError(response);
  }
};

export const getLarkStatus = async (): Promise<LarkStatusResponse> => {
  const response = await fetch(`${API_BASE_URL}/lark/status`);
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const pushReviewToLark = async (
  payload: LarkPushReviewPayload,
): Promise<{ ok: boolean; message_id?: string }> => {
  const response = await fetch(`${API_BASE_URL}/lark/push-review`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    await parseApiError(response);
  }

  return response.json();
};

export type SocialStatusResponse = {
  weibo_publish_enabled: boolean;
  weibo: {
    configured?: boolean;
    logged_in?: boolean;
    reason?: string;
    dry_run?: boolean;
    current_url?: string;
  };
  weibo_oauth_configured?: boolean;
  x_publish_enabled: boolean;
  x_oauth_configured?: boolean;
  x: {
    configured?: boolean;
    logged_in?: boolean;
    reason?: string;
    dry_run?: boolean;
    current_url?: string;
  };
  x_sync_enabled: boolean;
  x_sync_username?: string | null;
  x_sync_interval_seconds: number;
  review_required: boolean;
  x_review_required: boolean;
  auto_on_complete: boolean;
  publish_engine: string;
  x_publish_engine: string;
  dry_run: boolean;
  x_dry_run: boolean;
};

export type WeiboPublishPayload = {
  user_id?: string;
  title?: string;
  content?: string;
  hashtags?: string[];
  image_url?: string;
  share_url?: string;
  review_approved?: boolean;
  version_id?: string;
};

export type WeiboPublishCreateResponse = {
  job_id: string;
  status: string;
};

export type PublishJobResponse = {
  job_id: string;
  platform: string;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | string;
  progress: string[];
  post_url?: string | null;
  error?: string | null;
  screenshot_path?: string | null;
  created_at: number;
  updated_at: number;
  payload_summary?: Record<string, unknown>;
};

export const getSocialStatus = async (
  forceRefresh = false,
  userId?: string,
): Promise<SocialStatusResponse> => {
  const params = new URLSearchParams();
  if (forceRefresh) {
    params.set('force_refresh', 'true');
  }
  if (userId) {
    params.set('user_id', userId);
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`${API_BASE_URL}/social/status${query}`);
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export type WeiboLoginStartResponse = {
  session_id: string;
  logged_in: boolean;
  current_url: string;
  profile_path: string;
  viewport_width: number;
  viewport_height: number;
};

export type WeiboLoginStatusResponse = {
  session_id: string;
  logged_in: boolean;
  current_url: string;
  profile_path: string;
};

export const startWeiboLoginSession = async (
  userId: string,
): Promise<WeiboLoginStartResponse> => {
  const response = await fetch(`${API_BASE_URL}/social/weibo/login/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const closeWeiboLoginSession = async (
  sessionId: string,
): Promise<{ ok: boolean }> => {
  const response = await fetch(
    `${API_BASE_URL}/social/weibo/login/${encodeURIComponent(sessionId)}`,
    { method: 'DELETE' },
  );
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const confirmWeiboLogin = async (
  sessionId: string,
): Promise<WeiboLoginStatusResponse> => {
  const response = await fetch(
    `${API_BASE_URL}/social/weibo/login/${encodeURIComponent(sessionId)}/confirm`,
    { method: 'POST' },
  );
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const startXLoginSession = async (
  userId: string,
): Promise<WeiboLoginStartResponse> => {
  const response = await fetch(`${API_BASE_URL}/social/x/login/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const closeXLoginSession = async (
  sessionId: string,
): Promise<{ ok: boolean }> => {
  const response = await fetch(
    `${API_BASE_URL}/social/x/login/${encodeURIComponent(sessionId)}`,
    { method: 'DELETE' },
  );
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const confirmXLogin = async (
  sessionId: string,
): Promise<WeiboLoginStatusResponse> => {
  const response = await fetch(
    `${API_BASE_URL}/social/x/login/${encodeURIComponent(sessionId)}/confirm`,
    { method: 'POST' },
  );
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const publishToWeibo = async (
  payload: WeiboPublishPayload,
): Promise<WeiboPublishCreateResponse> => {
  const response = await fetch(`${API_BASE_URL}/social/publish/weibo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export type XPublishPayload = {
  user_id?: string;
  title?: string;
  content?: string;
  hashtags?: string[];
  image_url?: string;
  share_url?: string;
  review_approved?: boolean;
  version_id?: string;
};

export type XPublishCreateResponse = {
  job_id: string;
  status: string;
};

export type WeiboOAuthUserStatus = {
  connected: boolean;
  oauth_connected?: boolean;
  profile_ready?: boolean;
  user_id?: string;
  weibo_uid?: string | null;
  weibo_screen_name?: string | null;
  expires_at?: string;
  scope?: string | null;
  profile?: SocialStatusResponse['weibo'];
};

export type WeiboOAuthSessionResponse = {
  session_id: string;
  user_id: string;
  logged_in: boolean;
  oauth_completed: boolean;
  oauth_error?: string | null;
  weibo_screen_name?: string | null;
  current_url: string;
  profile_path: string;
  viewport_width: number;
  viewport_height: number;
};

export const startWeiboOAuthSession = async (
  userId: string,
): Promise<WeiboOAuthSessionResponse> => {
  const response = await fetch(`${API_BASE_URL}/social/weibo/oauth/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const getWeiboOAuthSessionStatus = async (
  sessionId: string,
): Promise<WeiboOAuthSessionResponse> => {
  const response = await fetch(
    `${API_BASE_URL}/social/weibo/oauth/session/${encodeURIComponent(sessionId)}`,
  );
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const confirmWeiboOAuthSession = async (
  sessionId: string,
): Promise<WeiboLoginStatusResponse> => {
  const response = await fetch(
    `${API_BASE_URL}/social/weibo/oauth/session/${encodeURIComponent(sessionId)}/confirm`,
    { method: 'POST' },
  );
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const closeWeiboOAuthSession = async (
  sessionId: string,
): Promise<{ ok: boolean }> => {
  const response = await fetch(
    `${API_BASE_URL}/social/weibo/oauth/session/${encodeURIComponent(sessionId)}`,
    { method: 'DELETE' },
  );
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const getWeiboOAuthUserStatus = async (
  userId: string,
  forceRefresh = false,
): Promise<WeiboOAuthUserStatus> => {
  const params = new URLSearchParams({ user_id: userId });
  if (forceRefresh) {
    params.set('force_refresh', 'true');
  }
  const response = await fetch(
    `${API_BASE_URL}/social/weibo/oauth/user?${params.toString()}`,
  );
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const disconnectWeiboOAuth = async (userId: string): Promise<void> => {
  const response = await fetch(
    `${API_BASE_URL}/social/weibo/oauth/user?user_id=${encodeURIComponent(userId)}`,
    { method: 'DELETE' },
  );
  if (!response.ok) {
    await parseApiError(response);
  }
};

export type XOAuthUserStatus = {
  connected: boolean;
  oauth_connected?: boolean;
  profile_ready?: boolean;
  user_id: string;
  x_user_id?: string | null;
  x_username?: string | null;
  expires_at?: string;
  has_refresh_token?: boolean;
  scope?: string | null;
  profile?: SocialStatusResponse['x'];
};

export type XOAuthSessionResponse = {
  session_id: string;
  user_id: string;
  logged_in: boolean;
  oauth_completed: boolean;
  oauth_error?: string | null;
  x_username?: string | null;
  authorize_url?: string;
  browserless?: boolean;
  current_url: string;
  profile_path: string;
  viewport_width: number;
  viewport_height: number;
};

export const startXOAuthSession = async (
  userId: string,
): Promise<XOAuthSessionResponse> => {
  const response = await fetch(`${API_BASE_URL}/social/x/oauth/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const getXOAuthSessionStatus = async (
  sessionId: string,
): Promise<XOAuthSessionResponse> => {
  const response = await fetch(
    `${API_BASE_URL}/social/x/oauth/session/${encodeURIComponent(sessionId)}`,
  );
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const confirmXOAuthSession = async (
  sessionId: string,
): Promise<WeiboLoginStatusResponse> => {
  const response = await fetch(
    `${API_BASE_URL}/social/x/oauth/session/${encodeURIComponent(sessionId)}/confirm`,
    { method: 'POST' },
  );
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const closeXOAuthSession = async (
  sessionId: string,
): Promise<{ ok: boolean }> => {
  const response = await fetch(
    `${API_BASE_URL}/social/x/oauth/session/${encodeURIComponent(sessionId)}`,
    { method: 'DELETE' },
  );
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const getXOAuthUserStatus = async (
  userId: string,
  forceRefresh = false,
): Promise<XOAuthUserStatus> => {
  const params = new URLSearchParams({ user_id: userId });
  if (forceRefresh) {
    params.set('force_refresh', 'true');
  }
  const response = await fetch(
    `${API_BASE_URL}/social/x/oauth/user?${params.toString()}`,
  );
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const disconnectXOAuth = async (userId: string): Promise<void> => {
  const response = await fetch(
    `${API_BASE_URL}/social/x/oauth/user?user_id=${encodeURIComponent(userId)}`,
    { method: 'DELETE' },
  );
  if (!response.ok) {
    await parseApiError(response);
  }
};

export const publishToX = async (
  payload: XPublishPayload,
): Promise<XPublishCreateResponse> => {
  const response = await fetch(`${API_BASE_URL}/social/publish/x`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const getPublishJobStatus = async (
  jobId: string,
): Promise<PublishJobResponse> => {
  const response = await fetch(
    `${API_BASE_URL}/social/publish/${encodeURIComponent(jobId)}`,
  );
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export const triggerXSyncOnce = async (): Promise<Record<string, unknown>> => {
  const response = await fetch(`${API_BASE_URL}/social/sync/x`, {
    method: 'POST',
  });
  if (!response.ok) {
    await parseApiError(response);
  }
  return response.json();
};

export type HotspotPlatform = 'weibo' | 'xhs' | 'douyin' | 'x' | 'reddit';

export type HotspotAnalyzeRequest = {
  keyword?: string;
  platforms?: HotspotPlatform[];
  max_items_per_platform?: number;
  locale?: string;
};

export type HotspotTrend = 'rising' | 'stable' | 'falling' | 'unknown';

export type HotspotItem = {
  id: string;
  platform: HotspotPlatform;
  title: string;
  summary: string;
  promotion_relevance?: string;
  heat_score: number;
  trend: HotspotTrend;
  source_url: string;
  published_at?: string | null;
  tags: string[];
  suspicious?: boolean;
};

export type TrendPoint = {
  date: string;
  count: number;
  avg_heat: number;
};

export type PlatformStat = {
  platform: HotspotPlatform;
  count: number;
  avg_heat: number;
};

export type HotspotAnalysisResult = {
  keyword: string;
  generated_at: string;
  platforms: HotspotPlatform[];
  summary: string;
  hotspots: HotspotItem[];
  trend_series: TrendPoint[];
  platform_stats: PlatformStat[];
  cross_platform_hotspots?: string[];
  marketing_insights?: string[];
  data_source_notes?: string;
  partial_errors: Record<string, string>;
};

export type HotspotSSEMessage = {
  type: string;
  data: Record<string, unknown>;
};

export const createHotspotAnalyzeStreamRequest = (
  payload: HotspotAnalyzeRequest = {},
  signal?: AbortSignal,
) =>
  fetch(`${API_BASE_URL}/social-hotspots/analyze/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
    signal,
  });

export const streamSocialHotspotsAnalyze = async (options: {
  payload?: HotspotAnalyzeRequest;
  signal?: AbortSignal;
  onEvent: (message: HotspotSSEMessage) => void;
}): Promise<HotspotAnalysisResult | null> => {
  const response = await createHotspotAnalyzeStreamRequest(
    options.payload,
    options.signal,
  );
  if (!response.ok) {
    await parseApiError(response);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    return null;
  }

  let finalResult: HotspotAnalysisResult | null = null;
  await parseSSEStream({
    reader,
    parseMessage: (payload) => JSON.parse(payload) as HotspotSSEMessage,
    onMessage: (message) => {
      options.onEvent(message);
      if (message.type === "result") {
        finalResult = message.data as unknown as HotspotAnalysisResult;
      }
    },
    onParseError: (error) => {
      console.error("热点 SSE 解析失败:", error);
    },
  });

  return finalResult;
};
