import { NextResponse, type NextRequest } from 'next/server';

/** Auth.js session cookie names (dev + prod + legacy NextAuth). */
export const AUTH_SESSION_COOKIE_NAMES = [
  'authjs.session-token',
  '__Secure-authjs.session-token',
  'next-auth.session-token',
  '__Secure-next-auth.session-token',
] as const;

export const hasAuthSessionCookie = (request: NextRequest): boolean =>
  AUTH_SESSION_COOKIE_NAMES.some((name) => request.cookies.has(name));

export const clearAuthSessionCookies = (
  request: NextRequest,
  response: NextResponse,
): NextResponse => {
  for (const name of AUTH_SESSION_COOKIE_NAMES) {
    if (!request.cookies.has(name)) {
      continue;
    }
    response.cookies.set(name, '', {
      maxAge: 0,
      path: '/',
      httpOnly: true,
      sameSite: 'lax',
    });
  }
  return response;
};
