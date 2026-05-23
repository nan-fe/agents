import { prisma } from '@/lib/prisma';
import { hashPassword, verifyPassword } from '@/lib/password';

const USERNAME_PATTERN = /^[a-zA-Z0-9_]{3,32}$/;
const MIN_PASSWORD_LENGTH = 6;

export type AuthUser = {
  id: string;
  username: string;
  name: string;
};

export type RegisterInput = {
  username: string;
  password: string;
  name?: string;
};

export type RegisterResult =
  | { ok: true; user: AuthUser }
  | { ok: false; error: string };

export const validateUsername = (username: string): string | null => {
  const normalized = username.trim();
  if (!normalized) {
    return '请输入账号。';
  }
  if (!USERNAME_PATTERN.test(normalized)) {
    return '账号需为 3–32 位字母、数字或下划线。';
  }
  return null;
};

export const validatePassword = (password: string): string | null => {
  if (!password) {
    return '请输入密码。';
  }
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `密码至少 ${MIN_PASSWORD_LENGTH} 位。`;
  }
  return null;
};

export const verifyUserCredentials = async (
  username: string,
  password: string,
): Promise<AuthUser | null> => {
  const normalizedUsername = username.trim();
  const user = await prisma.user.findUnique({
    where: { username: normalizedUsername },
  });

  if (!user) {
    return null;
  }

  const isValid = await verifyPassword(password, user.passwordHash);
  if (!isValid) {
    return null;
  }

  return {
    id: user.id,
    username: user.username,
    name: user.name ?? user.username,
  };
};

export const registerUser = async (
  input: RegisterInput,
): Promise<RegisterResult> => {
  const username = input.username.trim();
  const password = input.password;
  const name = input.name?.trim() || username;

  const usernameError = validateUsername(username);
  if (usernameError) {
    return { ok: false, error: usernameError };
  }

  const passwordError = validatePassword(password);
  if (passwordError) {
    return { ok: false, error: passwordError };
  }

  const existingUser = await prisma.user.findUnique({
    where: { username },
  });
  if (existingUser) {
    return { ok: false, error: '该账号已被注册，请更换账号或直接登录。' };
  }

  const passwordHash = await hashPassword(password);
  const user = await prisma.user.create({
    data: {
      username,
      passwordHash,
      name,
    },
  });

  return {
    ok: true,
    user: {
      id: user.id,
      username: user.username,
      name: user.name ?? user.username,
    },
  };
};
