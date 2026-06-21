import { prisma } from '@/lib/prisma';
import { hashPassword, verifyPassword } from '@/lib/password';

const USERNAME_PATTERN = /^[a-zA-Z0-9_]{3,32}$/;
const MIN_PASSWORD_LENGTH = 6;
const MAX_USERNAME_LENGTH = 32;

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

export type OAuthUserInput = {
  provider: string;
  providerAccountId: string;
  type: string;
  email?: string | null;
  name?: string | null;
  image?: string | null;
  preferredUsername?: string | null;
  refresh_token?: string | null;
  access_token?: string | null;
  expires_at?: number | null;
  token_type?: string | null;
  scope?: string | null;
  id_token?: string | null;
  session_state?: string | null;
};

export type OAuthProviderKind = 'github' | 'google';

const sanitizeUsernameBase = (value: string): string => {
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .replace(/_+/g, '_');

  if (!normalized) {
    return '';
  }

  return normalized.slice(0, MAX_USERNAME_LENGTH);
};

const buildFallbackUsername = (
  provider: OAuthProviderKind,
  providerAccountId: string,
): string => {
  const suffix = providerAccountId.replace(/[^a-zA-Z0-9]/g, '').slice(0, 8);
  const prefix = provider === 'github' ? 'gh' : 'google';
  const candidate = `${prefix}_${suffix || 'user'}`.slice(0, MAX_USERNAME_LENGTH);

  if (USERNAME_PATTERN.test(candidate)) {
    return candidate;
  }

  return `${prefix}_user`.slice(0, MAX_USERNAME_LENGTH);
};

export const deriveUsername = (
  provider: OAuthProviderKind,
  input: {
    preferredUsername?: string | null;
    email?: string | null;
    providerAccountId: string;
  },
): string => {
  const candidates: string[] = [];

  if (input.preferredUsername) {
    candidates.push(sanitizeUsernameBase(input.preferredUsername));
  }

  if (input.email) {
    const localPart = input.email.split('@')[0] ?? '';
    candidates.push(sanitizeUsernameBase(localPart));
  }

  candidates.push(buildFallbackUsername(provider, input.providerAccountId));

  for (const candidate of candidates) {
    if (candidate && USERNAME_PATTERN.test(candidate)) {
      return candidate;
    }
  }

  return buildFallbackUsername(provider, input.providerAccountId);
};

const resolveUniqueUsername = async (baseUsername: string): Promise<string> => {
  let candidate = baseUsername;
  let suffix = 2;

  while (true) {
    const existing = await prisma.user.findUnique({
      where: { username: candidate },
      select: { id: true },
    });

    if (!existing) {
      return candidate;
    }

    const suffixText = `_${suffix}`;
    const trimmedBase = baseUsername.slice(
      0,
      Math.max(3, MAX_USERNAME_LENGTH - suffixText.length),
    );
    candidate = `${trimmedBase}${suffixText}`;
    suffix += 1;
  }
};

const normalizeEmail = (email?: string | null): string | null => {
  if (!email) {
    return null;
  }

  const normalized = email.trim().toLowerCase();
  return normalized || null;
};

const toAuthUser = (user: {
  id: string;
  username: string;
  name: string | null;
}): AuthUser => ({
  id: user.id,
  username: user.username,
  name: user.name ?? user.username,
});

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

  if (!user || !user.passwordHash) {
    return null;
  }

  const isValid = await verifyPassword(password, user.passwordHash);
  if (!isValid) {
    return null;
  }

  return toAuthUser(user);
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
    user: toAuthUser(user),
  };
};

export const findOrCreateOAuthUser = async (
  input: OAuthUserInput,
): Promise<AuthUser> => {
  const email = normalizeEmail(input.email);
  const provider = input.provider as OAuthProviderKind;

  const existingAccount = await prisma.account.findUnique({
    where: {
      provider_providerAccountId: {
        provider: input.provider,
        providerAccountId: input.providerAccountId,
      },
    },
    include: { user: true },
  });

  if (existingAccount) {
    const updates: {
      email?: string;
      name?: string;
      image?: string;
    } = {};

    if (email && !existingAccount.user.email) {
      updates.email = email;
    }
    if (input.name && !existingAccount.user.name) {
      updates.name = input.name;
    }
    if (input.image && !existingAccount.user.image) {
      updates.image = input.image;
    }

    if (Object.keys(updates).length > 0) {
      const updatedUser = await prisma.user.update({
        where: { id: existingAccount.user.id },
        data: updates,
      });
      return toAuthUser(updatedUser);
    }

    return toAuthUser(existingAccount.user);
  }

  if (email) {
    const existingUser = await prisma.user.findUnique({
      where: { email },
    });

    if (existingUser) {
      await prisma.account.create({
        data: {
          userId: existingUser.id,
          type: input.type,
          provider: input.provider,
          providerAccountId: input.providerAccountId,
          refresh_token: input.refresh_token,
          access_token: input.access_token,
          expires_at: input.expires_at,
          token_type: input.token_type,
          scope: input.scope,
          id_token: input.id_token,
          session_state: input.session_state,
        },
      });

      const updates: {
        name?: string;
        image?: string;
      } = {};

      if (input.name && !existingUser.name) {
        updates.name = input.name;
      }
      if (input.image && !existingUser.image) {
        updates.image = input.image;
      }

      if (Object.keys(updates).length > 0) {
        const updatedUser = await prisma.user.update({
          where: { id: existingUser.id },
          data: updates,
        });
        return toAuthUser(updatedUser);
      }

      return toAuthUser(existingUser);
    }
  }

  const baseUsername = deriveUsername(provider, {
    preferredUsername: input.preferredUsername,
    email,
    providerAccountId: input.providerAccountId,
  });
  const username = await resolveUniqueUsername(baseUsername);
  const name = input.name?.trim() || username;

  const user = await prisma.user.create({
    data: {
      username,
      email,
      name,
      image: input.image ?? null,
      accounts: {
        create: {
          type: input.type,
          provider: input.provider,
          providerAccountId: input.providerAccountId,
          refresh_token: input.refresh_token,
          access_token: input.access_token,
          expires_at: input.expires_at,
          token_type: input.token_type,
          scope: input.scope,
          id_token: input.id_token,
          session_state: input.session_state,
        },
      },
    },
  });

  return toAuthUser(user);
};
