import { createProject, finalizeProject } from '@/services/api';
import {
  bindProjectId,
  getOrCreateSessionId,
  getProjectId,
  resetProjectAndSession,
} from './session';

/** 侧栏「新对话」：finalize 当前项目 → 新 session + 新 project_id。 */
export const startNewConversation = async (
  userId: string,
): Promise<{
  sessionId: string;
  projectId: string;
}> => {
  const projectId = getProjectId();
  const sessionId = getOrCreateSessionId();

  if (projectId && userId) {
    await finalizeProject({
      project_id: projectId,
      session_id: sessionId,
      user_id: userId,
    });
  }

  const { sessionId: nextSessionId } = resetProjectAndSession();
  const created = await createProject(userId);
  bindProjectId(created.project_id);

  return {
    sessionId: nextSessionId,
    projectId: created.project_id,
  };
};

/** 删除当前对话后：不 finalize，直接新 session + project_id。 */
export const startConversationAfterDelete = async (
  userId: string,
): Promise<{
  sessionId: string;
  projectId: string;
}> => {
  const { sessionId: nextSessionId } = resetProjectAndSession();
  const created = await createProject(userId);
  bindProjectId(created.project_id);

  return {
    sessionId: nextSessionId,
    projectId: created.project_id,
  };
};
