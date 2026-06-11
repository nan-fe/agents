import { getProjects, type ProjectListItem } from '../services/api';
import type { ThreadItem } from '../types/conversation';
import { loadProjectConversationState, type LoadedProjectState } from './project-conversation';

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

export const bootstrapInitialConversation =
  async (): Promise<BootstrapConversationResult> => {
    try {
      const { projects } = await getProjects();
      if (projects.length === 0) {
        return { status: 'empty' };
      }

      const activeProject = projects[0];
      const loaded = await loadProjectConversationState(activeProject.project_id);
      return {
        status: 'loaded',
        projectId: activeProject.project_id,
        thread: loaded.thread,
        latestVersionIndex: loaded.latestVersionIndex,
      };
    } catch (error) {
      console.error('加载项目列表失败:', error);
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
    return { status: 'error' };
  }
};

export const loadHistoryProjectList = async (): Promise<ProjectListItem[]> => {
  try {
    const { projects } = await getProjects();
    return projects.filter((item) => item.version_count > 0);
  } catch (error) {
    console.error('加载历史对话失败:', error);
    return [];
  }
};
