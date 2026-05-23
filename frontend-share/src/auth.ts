import NextAuth from 'next-auth';
import Credentials from 'next-auth/providers/credentials';

import { authConfig } from '@/auth.config';
import { verifyUserCredentials } from '@/lib/user-service';

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  providers: [
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
