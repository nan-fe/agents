import type { Session } from 'next-auth';

export const getStudioUserId = (session: Session | null | undefined): string => {
  const user = session?.user as { id?: string; username?: string } | undefined;
  return (user?.username ?? user?.id ?? '').trim();
};
