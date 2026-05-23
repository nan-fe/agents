/** 后端续传不可恢复时返回的业务错误码（见 main._yield_resume_error） */
export const RESUME_FAILED_CODE = "RESUME_FAILED" as const;

export type DialogStreamResult = {
  content?: string;
  title?: string;
  hashtags?: string[];
  image_url?: string;
  message?: string;
  error_code?: string;
};

/** SSE message 最小结构，兼容 log / result 分支 */
export type StreamMessage = {
  type?: string;
  data?: DialogStreamResult & { from?: string; message?: string };
};

export const isResumeFailureLogEvent = (event: StreamMessage): boolean =>
  event.type === "log" &&
  typeof event.data?.message === "string" &&
  event.data.message.includes("续传失败");

export const isResumeFailureStreamEvent = (event: StreamMessage): boolean =>
  event.type === "result" && event.data?.error_code === RESUME_FAILED_CODE;

export const isResumeFailedResult = (
  result: DialogStreamResult | null | undefined,
): result is DialogStreamResult & {
  error_code: typeof RESUME_FAILED_CODE;
  message?: string;
} => result?.error_code === RESUME_FAILED_CODE;
