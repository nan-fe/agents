import type { NextAuthConfig } from 'next-auth';

import { getAuthSecret } from '@/lib/auth-secret';

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
    jwt({ token, user }) {
      if (user?.username) {
        token.username = user.username;
      }
      return token;
    },
    session({ session, token }) {
      if (!session.user) {
        return session;
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
