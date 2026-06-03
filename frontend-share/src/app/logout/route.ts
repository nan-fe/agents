import { signOut } from '@/auth';

/** 创作台通过 `window.location.assign('/logout')` 发起 GET，须同时支持 GET/POST */
const logout = () => signOut({ redirectTo: '/' });

export const GET = logout;
export const POST = logout;
