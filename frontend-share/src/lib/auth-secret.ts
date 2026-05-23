export const getAuthSecret = (): string | undefined => {
  const secret = process.env.AUTH_SECRET?.trim();
  if (secret) {
    return secret;
  }

  if (process.env.NODE_ENV === 'development') {
    return 'dev-auth-secret-change-me';
  }

  return undefined;
};
