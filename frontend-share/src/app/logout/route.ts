import { signOut } from '@/auth';

export const POST = async () => signOut({ redirectTo: '/' });
