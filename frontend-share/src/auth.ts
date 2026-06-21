import type { NextAuthConfig } from 'next-auth';

import { authConfig } from '@/auth.config';
import { verifyUserCredentials } from '@/lib/user-service';
import { OAUTH_PROVIDERS } from '@/lib/oauth-providers';
import GitHub from 'next-auth/providers/github';
import Google from 'next-auth/providers/google';
import Credentials from 'next-auth/providers/credentials';
import NextAuth from 'next-auth';

const oauthProviders = [
  ...(OAUTH_PROVIDERS.includes('github')
    ? [
        GitHub({
          clientId: process.env.AUTH_GITHUB_ID,
          clientSecret: process.env.AUTH_GITHUB_SECRET,
        }),
      ]
    : []),
  ...(OAUTH_PROVIDERS.includes('google')
    ? [
        Google({
          clientId: process.env.AUTH_GOOGLE_ID,
          clientSecret: process.env.AUTH_GOOGLE_SECRET,
        }),
      ]
    : []),
];

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  providers: [
    ...oauthProviders,
    Credentials({
      credentials: {
        username: { label: 'Username', type: 'text' },
        password: { label: 'Password', type: 'password' },
      },
      authorize: async (credentials) => {
        const username =
          typeof credentials?.username === 'string' ? credentials.username : '';
        const password =
          typeof credentials?.password === 'string' ? credentials.password : '';

        if (!username || !password) {
          return null;
        }

        const matchedUser = await verifyUserCredentials(username, password);
        if (!matchedUser) {
          return null;
        }

        return {
          id: matchedUser.id,
          name: matchedUser.name,
          username: matchedUser.username,
        };
      },
    }),
  ],
});
