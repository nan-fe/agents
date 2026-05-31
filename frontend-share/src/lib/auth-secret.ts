const PLACEHOLDER_SECRETS = new Set(['replace-with-openssl-rand-base64-32']);

const DEV_AUTH_SECRET = 'dev-auth-secret-change-me';

export const getAuthSecret = (): string | undefined => {
  const secret = process.env.AUTH_SECRET?.trim();

  if (process.env.NODE_ENV === 'development') {
    if (secret) {
      return secret;
    }
    return DEV_AUTH_SECRET;
  }

  if (secret && !PLACEHOLDER_SECRETS.has(secret)) {
    return secret;
  }

  return undefined;
};
