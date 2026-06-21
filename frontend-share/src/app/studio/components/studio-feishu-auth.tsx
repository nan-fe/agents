"use client";

import { useSession } from 'next-auth/react';
import FeishuOAuthConnect from './feishu-oauth-connect';

const StudioFeishuAuth = () => {
  const { data: session } = useSession();
  const userId = session?.user?.username ?? session?.user?.id ?? '';

  if (!userId) {
    return null;
  }

  return <FeishuOAuthConnect userId={userId} variant="compact" />;
};

export default StudioFeishuAuth;
