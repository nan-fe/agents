import { signOut } from '@/auth';

export const GET = async () => signOut({ redirectTo: '/' });

export const POST = async () => signOut({ redirectTo: '/' });
