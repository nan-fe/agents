import { getProjects, reportError, type ProjectListItem } from '@/services/api';
import type { ThreadItem } from '@/types/conversation';
import { parseApiDateTime } from '@/lib/timestamp';
import { loadProjectConversationState, type LoadedProjectState } from './project-conversation';
import { getProjectId } from './session';

export type BootstrapConversationResult =
  | { status: 'empty' }
  | {
      status: 'loaded';
      projectId: string;
      thread: ThreadItem[];
      latestVersionIndex: number;
    }
  | { status: 'error' };

export type SwitchHistoryProjectResult =
  | { status: 'success'; projectId: string; loaded: LoadedProjectState }
  | { status: 'error' };

const loadBoundProject = async (
  projectId: string,
): Promise<BootstrapConversationResult> => {
  const loaded = await loadProjectConversationState(projectId);
  return {
    status: 'loaded',
    projectId,
    thread: loaded.thread,
    latestVersionIndex: loaded.latestVersionIndex,
  };
};

export const bootstrapInitialConversation =
  async (): Promise<BootstrapConversationResult> => {
    try {
      const storedProjectId = getProjectId();
      const { projects } = await getProjects();

      // 新对话：POST /projects 仅分配 id，尚未出现在列表 → 空白欢迎页
      if (
        storedProjectId &&
        !projects?.some((item) => item.project_id === storedProjectId)
      ) {
        return loadBoundProject(storedProjectId ?? '');
      }

      if (projects?.length === 0) {
        return storedProjectId
          ? loadBoundProject(storedProjectId ?? '')
          : { status: 'empty' };
      }

      const activeProject =
        (storedProjectId
          ? projects?.find((item) => item.project_id === storedProjectId)
          : undefined) ?? projects?.[0];
      return loadBoundProject(activeProject?.project_id ?? '');
    } catch (error) {
      console.error('加载项目列表失败:', error);
      await reportError(error, 'session/bootstrapConversation');
      return { status: 'error' };
    }
  };

export const switchHistoryProject = async (
  projectId: string,
): Promise<SwitchHistoryProjectResult> => {
  try {
    const loaded = await loadProjectConversationState(projectId);
    return { status: 'success', projectId, loaded };
  } catch (error) {
    console.error('切换对话失败:', error);
    await reportError(error, 'session/switchHistoryProject', { projectId });
    return { status: 'error' };
  }
};

const sortProjectsByLastAccessed = (
  projects: ProjectListItem[],
): ProjectListItem[] =>
  [...projects].sort(
    (a, b) =>
      parseApiDateTime(b.last_accessed_at).getTime() -
      parseApiDateTime(a.last_accessed_at).getTime(),
  );

export const loadHistoryProjectList = async (): Promise<ProjectListItem[]> => {
  try {
    const { projects } = await getProjects();
    return sortProjectsByLastAccessed(
      projects?.filter((item) => item.version_count > 0) ?? [],
    );
  } catch (error) {
    console.error('加载历史对话失败:', error);
    await reportError(error, 'session/loadHistoryProjectList');
    return [];
  }
};
