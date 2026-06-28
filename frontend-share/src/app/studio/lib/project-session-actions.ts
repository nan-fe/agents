import { deleteProject, getProjects, reportError, type ProjectListItem } from '@/services/api';
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
  userId: string,
): Promise<BootstrapConversationResult> => {
  if (!projectId) {
    return { status: 'empty' };
  }

  try {
    const loaded = await loadProjectConversationState(projectId, userId);
    return {
      status: 'loaded',
      projectId,
      thread: loaded.thread,
      latestVersionIndex: loaded.latestVersionIndex,
    };
  } catch (error) {
    console.error('加载对话失败:', error, { projectId, userId });
    await reportError(error, 'session/loadBoundProject', { projectId, userId });
    return { status: 'error' };
  }
};

export const bootstrapInitialConversation = async (
  userId: string,
): Promise<BootstrapConversationResult> => {
  if (!userId) {
    return { status: 'empty' };
  }

  try {
    const storedProjectId = getProjectId();
    const { projects } = await getProjects(userId);

    if (
      storedProjectId &&
      !projects?.some((item) => item.project_id === storedProjectId)
    ) {
      // 仅客户端分配、尚未落库或已失效的 project_id，不请求 GET /projects/{id}
      return { status: 'empty' };
    }

    if (projects?.length === 0) {
      return { status: 'empty' };
    }

    const activeProject =
      (storedProjectId
        ? projects?.find((item) => item.project_id === storedProjectId)
        : undefined) ?? projects?.[0];
    return await loadBoundProject(activeProject?.project_id ?? '', userId);
  } catch (error) {
    console.error('加载项目列表失败:', error);
    await reportError(error, 'session/bootstrapConversation', { userId });
    return { status: 'error' };
  }
};

export const switchHistoryProject = async (
  projectId: string,
  userId: string,
): Promise<SwitchHistoryProjectResult> => {
  if (!userId) {
    return { status: 'error' };
  }

  try {
    const loaded = await loadProjectConversationState(projectId, userId);
    return { status: 'success', projectId, loaded };
  } catch (error) {
    console.error('切换对话失败:', error);
    await reportError(error, 'session/switchHistoryProject', { projectId, userId });
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

export const loadHistoryProjectList = async (
  userId: string,
): Promise<ProjectListItem[]> => {
  if (!userId) {
    return [];
  }

  try {
    const { projects } = await getProjects(userId);
    return sortProjectsByLastAccessed(
      projects?.filter((item) => item.version_count > 0) ?? [],
    );
  } catch (error) {
    console.error('加载历史对话失败:', error);
    await reportError(error, 'session/loadHistoryProjectList', { userId });
    return [];
  }
};

export const deleteHistoryProject = async (
  projectId: string,
  userId: string,
): Promise<boolean> => {
  if (!userId) {
    return false;
  }

  try {
    await deleteProject(projectId, userId);
    return true;
  } catch (error) {
    console.error('删除历史对话失败:', error);
    await reportError(error, 'session/deleteHistoryProject', { projectId, userId });
    return false;
  }
};
