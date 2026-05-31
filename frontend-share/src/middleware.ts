import { getToken } from 'next-auth/jwt';
import { NextResponse, type NextRequest } from 'next/server';

import { getAuthSecret } from '@/lib/auth-secret';
import {
  clearAuthSessionCookies,
  hasAuthSessionCookie,
} from '@/lib/auth-session-cookies';

const resolveSession = async (request: NextRequest) => {
  const token = await getToken({
    req: request,
    secret: getAuthSecret(),
  });

  return {
    token,
    isLoggedIn: !!token,
  };
};

export const middleware = async (request: NextRequest) => {
  const { nextUrl } = request;
  const pathname = nextUrl.pathname;
  const isStudio = pathname === '/studio' || pathname.startsWith('/studio/');
  const isLogin = pathname === '/login';
  const isRegister = pathname === '/register';

  const { token, isLoggedIn } = await resolveSession(request);

  if (hasAuthSessionCookie(request) && !token) {
    return clearAuthSessionCookies(request, NextResponse.next());
  }

  if (!isStudio && !isLogin && !isRegister) {
    return NextResponse.next();
  }

  if (isStudio && !isLoggedIn) {
    const loginUrl = new URL('/login', nextUrl.origin);
    loginUrl.searchParams.set('returnUrl', `${pathname}${nextUrl.search}`);
    return NextResponse.redirect(loginUrl);
  }

  if ((isLogin || isRegister) && isLoggedIn) {
    const returnUrl = nextUrl.searchParams.get('returnUrl') || '/studio';
    return NextResponse.redirect(new URL(returnUrl, nextUrl.origin));
  }

  return NextResponse.next();
};

export const config = {
  matcher: [
    '/',
    '/studio',
    '/studio/:path*',
    '/login',
    '/register',
    '/share/:path*',
  ],
};
