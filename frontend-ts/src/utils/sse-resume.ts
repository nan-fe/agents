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

export type StreamLogData = {
  from?: string;
  message?: string;
  agent_key?: string;
  intent?: string;
  intent_label?: string;
};

export type StreamMetaData = {
  intent_labels: Record<string, string>;
  agent_labels: Record<string, string>;
};

/** SSE message 最小结构，兼容 log / meta / result 分支 */
export type StreamMessage = {
  type?: string;
  data?: (DialogStreamResult & StreamLogData) | StreamMetaData;
};

const isLogData = (
  data: StreamMessage["data"],
): data is DialogStreamResult & StreamLogData =>
  Boolean(data && "message" in data);

const isResultData = (
  data: StreamMessage["data"],
): data is DialogStreamResult & StreamLogData =>
  Boolean(data && "error_code" in data);

export const isResumeFailureLogEvent = (event: StreamMessage): boolean =>
  event.type === "log" &&
  isLogData(event.data) &&
  typeof event.data.message === "string" &&
  event.data.message.includes("续传失败");

export const isResumeFailureStreamEvent = (event: StreamMessage): boolean =>
  event.type === "result" &&
  isResultData(event.data) &&
  event.data.error_code === RESUME_FAILED_CODE;

export const isResumeFailedResult = (
  result: DialogStreamResult | null | undefined,
): result is DialogStreamResult & {
  error_code: typeof RESUME_FAILED_CODE;
  message?: string;
} => result?.error_code === RESUME_FAILED_CODE;
