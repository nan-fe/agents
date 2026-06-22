import { getToken } from 'next-auth/jwt';
import { NextRequest } from 'next/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { middleware } from '@/middleware';

vi.mock('next-auth/jwt', () => ({
  getToken: vi.fn(),
}));

const mockedGetToken = vi.mocked(getToken);

const requestFor = (pathname: string, search = '') =>
  new NextRequest(new URL(`http://localhost:3000${pathname}${search}`));

describe('middleware auth routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.AUTH_SECRET = 'test-auth-secret-minimum-32-characters';
  });

  it('redirects unauthenticated users away from /studio', async () => {
    mockedGetToken.mockResolvedValue(null);

    const response = await middleware(requestFor('/studio'));

    expect(response.status).toBe(307);
    expect(response.headers.get('location')).toBe(
      'http://localhost:3000/login?returnUrl=%2Fstudio',
    );
  });

  it('redirects authenticated users away from /login', async () => {
    mockedGetToken.mockResolvedValue({ sub: 'user-1' });

    const response = await middleware(requestFor('/login'));

    expect(response.status).toBe(307);
    expect(response.headers.get('location')).toBe('http://localhost:3000/studio');
  });

  it('honors returnUrl when redirecting authenticated users from /login', async () => {
    mockedGetToken.mockResolvedValue({ sub: 'user-1' });

    const response = await middleware(
      requestFor('/login', '?returnUrl=%2Fstudio%3Ftab%3D1'),
    );

    expect(response.headers.get('location')).toBe(
      'http://localhost:3000/studio?tab=1',
    );
  });

  it('passes through public routes without auth checks', async () => {
    mockedGetToken.mockResolvedValue(null);

    const response = await middleware(requestFor('/share/demo'));

    expect(response.status).toBe(200);
    expect(response.headers.get('location')).toBeNull();
  });
});
