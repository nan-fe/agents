import * as Sentry from '@sentry/nextjs';

import { isSentryEnabled } from '@/lib/sentry';

type NextFetchConfig = {
  next?: {
    revalidate?: number | false;
    tags?: string[];
  };
};

export type FetchWithReportInit = RequestInit &
  NextFetchConfig & {
    /** 是否上报非 2xx 响应；调用方会 throw 时建议 false，避免与 error boundary 重复 */
    reportHttpErrors?: boolean;
    /** 不报 Sentry 的 HTTP 状态码（如预期的 404） */
    ignoreStatuses?: number[];
    /** 为 true 时跳过 4xx，仅上报 5xx 与网络异常 */
    ignoreClientErrors?: boolean;
    /** 完全跳过 Sentry 上报 */
    skipReport?: boolean;
  };

const isClientError = (status: number) => status >= 400 && status < 500;

const shouldReportHttpError = (
  response: Response,
  {
    ignoreStatuses = [],
    ignoreClientErrors = false,
  }: Pick<FetchWithReportInit, 'ignoreStatuses' | 'ignoreClientErrors'>,
) => {
  if (response.ok || ignoreStatuses.includes(response.status)) {
    return false;
  }
  if (ignoreClientErrors && isClientError(response.status)) {
    return false;
  }
  return true;
};

const reportFetchFailure = (
  error: unknown,
  context: {
    url: string;
    method: string;
    status?: number;
    statusText?: string;
  },
) => {
  if (!isSentryEnabled()) {
    return;
  }

  Sentry.captureException(error, {
    extra: context,
    tags: {
      source: 'fetch-with-report',
    },
  });
};

/** 统一 fetch：网络异常与 HTTP 错误自动上报 Sentry */
export const fetchWithReport = async (
  input: RequestInfo | URL,
  init?: FetchWithReportInit,
): Promise<Response> => {
  const {
    reportHttpErrors = true,
    ignoreStatuses,
    ignoreClientErrors,
    skipReport = false,
    ...fetchInit
  } = init ?? {};

  const url = String(input);
  const method = fetchInit.method ?? 'GET';

  try {
    const response = await fetch(input, fetchInit);

    if (
      !skipReport &&
      reportHttpErrors &&
      shouldReportHttpError(response, { ignoreStatuses, ignoreClientErrors })
    ) {
      reportFetchFailure(
        new Error(`HTTP ${response.status}: ${method} ${url}`),
        {
          url,
          method,
          status: response.status,
          statusText: response.statusText,
        },
      );
    }

    return response;
  } catch (error) {
    if (!skipReport) {
      reportFetchFailure(error, { url, method });
    }
    throw error;
  }
};
