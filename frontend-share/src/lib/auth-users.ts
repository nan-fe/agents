import { timingSafeEqual } from 'crypto';

export type AuthUserRecord = {
  username: string;
  password: string;
  name?: string;
};

const parseAuthUserEntry = (entry: string): AuthUserRecord | null => {
  const trimmed = entry.trim();
  if (!trimmed) {
    return null;
  }

  const [credentials, name] = trimmed.split('|');
  const separatorIndex = credentials.indexOf(':');
  if (separatorIndex <= 0) {
    return null;
  }

  const username = credentials.slice(0, separatorIndex).trim();
  const password = credentials.slice(separatorIndex + 1).trim();
  if (!username || !password) {
    return null;
  }

  return {
    username,
    password,
    name: name?.trim() || username,
  };
};

export const parseAuthUsers = (): AuthUserRecord[] => {
  const raw = process.env.AUTH_USERS?.trim();
  if (!raw) {
    if (process.env.NODE_ENV === 'development') {
      return [{ username: 'demo', password: 'demo123', name: 'Demo User' }];
    }
    return [];
  }

  return raw
    .split(',')
    .map(parseAuthUserEntry)
    .filter((user): user is AuthUserRecord => user !== null);
};

const safeCompare = (left: string, right: string): boolean => {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);
  if (leftBuffer.length !== rightBuffer.length) {
    return false;
  }
  return timingSafeEqual(leftBuffer, rightBuffer);
};

export const findAuthUser = (
  username: string,
  password: string,
): AuthUserRecord | null => {
  const normalizedUsername = username.trim();
  const matchedUser = parseAuthUsers().find(
    (user) => user.username === normalizedUsername,
  );

  if (!matchedUser || !safeCompare(matchedUser.password, password)) {
    return null;
  }

  return matchedUser;
};
