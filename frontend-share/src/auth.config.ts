import type { NextAuthConfig } from 'next-auth';

import { getAuthSecret } from '@/lib/auth-secret';
import { findOrCreateOAuthUser } from '@/lib/user-service';

const isOAuthProvider = (provider?: string): boolean =>
  provider === 'github' || provider === 'google';

export const authConfig = {
  secret: getAuthSecret(),
  trustHost: true,
  session: {
    strategy: 'jwt',
    maxAge: 30 * 24 * 60 * 60,
  },
  pages: {
    signIn: '/login',
  },
  providers: [],
  callbacks: {
    async signIn({ user, account, profile }) {
      if (!account || account.provider === 'credentials') {
        return true;
      }

      if (!isOAuthProvider(account.provider)) {
        return false;
      }

      try {
        const preferredUsername =
          account.provider === 'github' && profile && 'login' in profile
            ? String(profile.login)
            : null;

        const authUser = await findOrCreateOAuthUser({
          provider: account.provider,
          providerAccountId: account.providerAccountId,
          type: account.type,
          email: user.email,
          name: user.name,
          image: user.image,
          preferredUsername,
          refresh_token: account.refresh_token,
          access_token: account.access_token,
          expires_at: account.expires_at,
          token_type: account.token_type,
          scope: account.scope,
          id_token: account.id_token,
          session_state:
            typeof account.session_state === 'string'
              ? account.session_state
              : null,
        });

        user.id = authUser.id;
        user.username = authUser.username;
        user.name = authUser.name;

        return true;
      } catch {
        return false;
      }
    },
    jwt({ token, user }) {
      if (user?.id) {
        token.sub = user.id;
      }

      if (user?.username) {
        token.username = user.username;
      }

      if (user?.name) {
        token.name = user.name;
      }

      return token;
    },
    session({ session, token }) {
      if (!session.user) {
        return session;
      }

      if (typeof token.sub === 'string') {
        session.user.id = token.sub;
      }

      if (typeof token.username === 'string') {
        session.user.username = token.username;
      }

      if (!session.user.name && typeof token.name === 'string') {
        session.user.name = token.name;
      }

      return session;
    },
  },
} satisfies NextAuthConfig;
