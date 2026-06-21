export type LarkNotificationMeta = {
  eligible: boolean;
  mode: 'auto' | 'prompt' | 'off' | string;
  configured: boolean;
  auto_sent: boolean;
  error?: string | null;
  prompt?: string;
};

export type DialogResultData = {
  content: string;
  title: string;
  hashtags: string[];
  image_url: string;
  message?: string;
  error_code?: string;
  project_id?: string;
  version_id?: string;
  version?: string;
  version_number?: number;
  review_approved?: boolean;
  review_feedback?: string;
  lark_notification?: LarkNotificationMeta;
};

export type AgentLogEntry = {
  agent_name: string;
  message: string;
  timestamp: string;
};

export type WelcomeThreadItem = {
  type: 'welcome';
  id: string;
  content: string;
  timestamp: number;
};

export type TurnThreadItem = {
  type: 'turn';
  id: string;
  versionId: number;
  userPrompt: string;
  userTimestamp: number;
  result: DialogResultData;
  completedTimestamp: number;
  logs: AgentLogEntry[];
};

export type PendingThreadItem = {
  type: 'pending';
  id: string;
  userPrompt: string;
  userTimestamp: number;
};

export type ThreadItem = WelcomeThreadItem | TurnThreadItem | PendingThreadItem;

export const WELCOME_MESSAGE_CONTENT =
  '哈喽～我是你的内容创作助手 小H。描述你想创作的小红书内容（例如：推荐一款适合学生党的平价防晒霜，清爽不油腻），我会为你生成标题、正文、话题标签与配图建议。';

export const createWelcomeThreadItem = (): WelcomeThreadItem => ({
  type: 'welcome',
  id: 'welcome',
  content: WELCOME_MESSAGE_CONTENT,
  timestamp: Date.now(),
});

export const createInitialThread = (): ThreadItem[] => [createWelcomeThreadItem()];
