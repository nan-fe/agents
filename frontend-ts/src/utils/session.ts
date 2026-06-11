export const SESSION_STORAGE_KEY = 'xhs_session_id';
export const PROJECT_STORAGE_KEY = 'xhs_project_id';

export const getSessionId = (): string | null =>
  sessionStorage.getItem(SESSION_STORAGE_KEY) ||
  localStorage.getItem(SESSION_STORAGE_KEY);

export const bindSessionId = (sessionId: string): void => {
  sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
};

export const getOrCreateSessionId = (): string => {
  const sessionStorageId = sessionStorage.getItem(SESSION_STORAGE_KEY);
  const localStorageId = localStorage.getItem(SESSION_STORAGE_KEY);
  const stableId = sessionStorageId || localStorageId;

  if (stableId) {
    if (!sessionStorageId) {
      sessionStorage.setItem(SESSION_STORAGE_KEY, stableId);
    }
    if (!localStorageId) {
      localStorage.setItem(SESSION_STORAGE_KEY, stableId);
    }
    return stableId;
  }

  const newId = `session_${Date.now()}`;
  sessionStorage.setItem(SESSION_STORAGE_KEY, newId);
  localStorage.setItem(SESSION_STORAGE_KEY, newId);
  return newId;
};

export const resetSessionId = (): string => {
  const newId = `session_${Date.now()}`;
  sessionStorage.setItem(SESSION_STORAGE_KEY, newId);
  localStorage.setItem(SESSION_STORAGE_KEY, newId);
  return newId;
};

export const getProjectId = (): string | null =>
  sessionStorage.getItem(PROJECT_STORAGE_KEY) ||
  localStorage.getItem(PROJECT_STORAGE_KEY);

export const bindProjectId = (projectId: string): void => {
  sessionStorage.setItem(PROJECT_STORAGE_KEY, projectId);
  localStorage.setItem(PROJECT_STORAGE_KEY, projectId);
};

export const clearProjectId = (): void => {
  sessionStorage.removeItem(PROJECT_STORAGE_KEY);
  localStorage.removeItem(PROJECT_STORAGE_KEY);
};

/** 新建会话：换 session_id，清本地 project_id（随后由 createProject 写入新的）。 */
export const resetProjectAndSession = (): { sessionId: string } => {
  clearProjectId();
  const sessionId = resetSessionId();
  return { sessionId };
};
