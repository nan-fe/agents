/**
 * API服务 - 封装SSE连接
 */

import type { components } from "../api/schema";
import { parseSSEStream } from "../utils/sse-parser";


export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.DEV ? "http://localhost:8000" : "");

export type UserInput = components["schemas"]["UserInput"];

export type DialogSSEType = {
  request: UserInput;
  log_callback: (from: string, message: string) => void;
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
  const { request, log_callback } = param;
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
      onMessage: (data: any) => {
        if (data.type === "log") {
          log_callback?.(data.data.from, data.data.message);
        } else if (data.type === "result") {
          finalResult = data.data;
        }
      },
      onParseError: (error) => {
        console.error("解析SSE消息失败:", error);
      },
    });

    return finalResult;
  } catch (error) {
    console.error("SSE连接错误:", error);
    throw error;
  }
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
    throw error;
  }
};
