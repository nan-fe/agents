/**
 * API服务 - 封装SSE连接
 */

import * as Sentry from "@sentry/react";
import type { components } from "../api/schema";
import { parseSSEStream } from "../utils/sse-parser";
import type { StreamIngestor } from "../utils/sse-stream-ingest";

/**
 * 上报已捕获错误到 Better Stack，附上操作名和可选上下文。
 * 在 try/catch 中用于不应静默吞掉的接口/业务错误。
 */
export const reportError = (
  error: unknown,
  operation: string,
  extra?: Record<string, unknown>,
): void => {
  Sentry.captureException(error, {
    tags: { operation },
    extra,
  });
};


export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.DEV ? "http://localhost:8000" : "");

const getShareBaseUrl = () => {
  if (import.meta.env.VITE_SHARE_BASE_URL) {
    return import.meta.env.VITE_SHARE_BASE_URL;
  }

  if (import.meta.env.DEV) {
    return "http://localhost:3000";
  }

  if (typeof window === "undefined") {
    return "";
  }

  // 创作台与分享页同域（经 frontend-share 入口），用当前 origin 即可
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

export type DialogSSEType = {
  request: UserInput;
  log_callback: (from: string, message: string) => void;
  streamIngestor?: StreamIngestor;
};

export const createProject = async (
  userId?: string,
): Promise<ProjectCreateResponse> => {
  const response = await fetch(`${API_BASE_URL}/projects`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(userId ? { user_id: userId } : {}),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
};

export const getProjects = async (
  userId?: string,
): Promise<ProjectListResponse> => {
  const query = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  const response = await fetch(`${API_BASE_URL}/projects${query}`);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
};

export const getProjectConversation = async (
  projectId: string,
): Promise<ProjectConversationResponse> => {
  const response = await fetch(
    `${API_BASE_URL}/projects/${encodeURIComponent(projectId)}`,
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
    reportError(error, "generateDialogContent");
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
    reportError(error, "rollbackToVersion", { session_id, version });
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
    reportError(error, "compareVersions", { session_id, version1, version2 });
    throw error;
  }
};
