import { getProjectConversation, type ProjectListItem } from '../services/api';
import {
  createInitialThread,
  createWelcomeThreadItem,
  type DialogResultData,
  type ThreadItem,
  type TurnThreadItem,
} from '../types/conversation';

export type StoredVersion = {
  version_id: string;
  version_label: string;
  version_number: number;
  user_input?: string | null;
  result: DialogResultData & Record<string, unknown>;
  created_at: string;
};

const normalizeResult = (raw: DialogResultData & Record<string, unknown>): DialogResultData => ({
  title: String(raw.title ?? ''),
  content: String(raw.content ?? ''),
  hashtags: Array.isArray(raw.hashtags) ? raw.hashtags.map(String) : [],
  image_url: String(raw.image_url ?? ''),
  message: raw.message ? String(raw.message) : undefined,
  error_code: raw.error_code ? String(raw.error_code) : undefined,
  project_id: raw.project_id ? String(raw.project_id) : undefined,
  version_id: raw.version_id ? String(raw.version_id) : undefined,
  version: raw.version ? String(raw.version) : undefined,
  version_number:
    typeof raw.version_number === 'number' ? raw.version_number : undefined,
});

export const buildThreadFromVersions = (versions: StoredVersion[]): ThreadItem[] => {
  if (versions.length === 0) {
    return createInitialThread();
  }

  const welcome = createWelcomeThreadItem();
  const turns: TurnThreadItem[] = versions.map((version, index) => {
    const completedAt = Date.parse(version.created_at) || Date.now();
    return {
      type: 'turn',
      id: `turn_${index}`,
      versionId: index,
      userPrompt: version.user_input ?? '',
      userTimestamp: completedAt,
      result: normalizeResult(version.result),
      completedTimestamp: completedAt,
      logs: [],
    };
  });

  return [welcome, ...turns];
};

export const castStoredVersions = (
  versions: Array<{
    version_id: string;
    version_label: string;
    version_number: number;
    user_input?: string | null;
    result: Record<string, unknown>;
    created_at: string;
  }>,
): StoredVersion[] => versions as StoredVersion[];

export type LoadedProjectState = {
  thread: ThreadItem[];
  latestVersionIndex: number;
};

export const loadProjectConversationState = async (
  projectId: string,
): Promise<LoadedProjectState> => {
  const conversation = await getProjectConversation(projectId);

  if (conversation.versions.length === 0) {
    return { thread: createInitialThread(), latestVersionIndex: -1 };
  }

  const thread = buildThreadFromVersions(castStoredVersions(conversation.versions));
  return {
    thread,
    latestVersionIndex: conversation.versions.length - 1,
  };
};

export const getProjectDisplayTitle = (project: ProjectListItem): string => {
  const summary = (project.project_summary ?? '').trim();
  if (summary) {
    return summary.length > 48 ? `${summary.slice(0, 48)}…` : summary;
  }

  const topic = (project.topic ?? '').trim();
  if (topic) {
    return topic;
  }

  if (project.version_count > 0) {
    return `对话 · ${project.version_count} 个版本`;
  }

  return '新对话';
};
