export const SESSION_STORAGE_KEY = 'xhs_session_id';

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
