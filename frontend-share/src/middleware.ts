import { getToken } from 'next-auth/jwt';
import { NextResponse, type NextRequest } from 'next/server';

import { getAuthSecret } from '@/lib/auth-secret';

export const middleware = async (request: NextRequest) => {
  const { nextUrl } = request;
  const pathname = nextUrl.pathname;
  const isStudio = pathname === '/studio' || pathname.startsWith('/studio/');
  const isLogin = pathname === '/login';
  const isRegister = pathname === '/register';

  if (!isStudio && !isLogin && !isRegister) {
    return NextResponse.next();
  }

  const token = await getToken({
    req: request,
    secret: getAuthSecret(),
  });
  const isLoggedIn = !!token;

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
  matcher: ['/studio', '/studio/:path*', '/login', '/register'],
};
