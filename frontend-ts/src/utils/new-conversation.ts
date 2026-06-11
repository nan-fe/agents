import { createProject, finalizeProject } from '../services/api';
import {
  bindProjectId,
  getOrCreateSessionId,
  getProjectId,
  resetProjectAndSession,
} from './session';

/** 侧栏「新对话」：finalize 当前项目 → 新 session + 新 project_id。 */
export const startNewConversation = async (): Promise<{
  sessionId: string;
  projectId: string;
}> => {
  const projectId = getProjectId();
  const sessionId = getOrCreateSessionId();

  if (projectId) {
    await finalizeProject({
      project_id: projectId,
      session_id: sessionId,
    });
  }

  const { sessionId: nextSessionId } = resetProjectAndSession();
  const created = await createProject();
  bindProjectId(created.project_id);

  return {
    sessionId: nextSessionId,
    projectId: created.project_id,
  };
};
