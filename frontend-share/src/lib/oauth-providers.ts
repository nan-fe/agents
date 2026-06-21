export type OAuthProviderId = 'github' | 'google';

export const OAUTH_PROVIDERS: OAuthProviderId[] = [];

if (process.env.AUTH_GITHUB_ID && process.env.AUTH_GITHUB_SECRET) {
  OAUTH_PROVIDERS.push('github');
}

if (process.env.AUTH_GOOGLE_ID && process.env.AUTH_GOOGLE_SECRET) {
  OAUTH_PROVIDERS.push('google');
}

export const hasOAuthProviders = (): boolean => OAUTH_PROVIDERS.length > 0;
