'use client';

import { useEffect } from 'react';
import { signOut } from 'next-auth/react';

import { clearStudioSession } from '@/app/studio/lib/session';

const LogoutPage = () => {
  useEffect(() => {
    clearStudioSession();
    void signOut({ redirectTo: '/' });
  }, []);

  return null;
};

export default LogoutPage;
