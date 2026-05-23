'use client';

import { useActionState } from 'react';
import { signIn } from 'next-auth/react';

type LoginState = {
  error: string | null;
};

const initialState: LoginState = { error: null };

type LoginFormProps = {
  returnUrl: string;
};

const loginAction = async (
  _prevState: LoginState,
  formData: FormData,
): Promise<LoginState> => {
  const username = String(formData.get('username') ?? '').trim();
  const password = String(formData.get('password') ?? '');
  const returnUrl = String(formData.get('returnUrl') ?? '/studio');

  if (!username || !password) {
    return { error: '请输入账号和密码。' };
  }

  const result = await signIn('credentials', {
    username,
    password,
    redirect: false,
  });

  if (result?.error) {
    return { error: '账号或密码错误，请重试。' };
  }

  window.location.assign(returnUrl);
  return { error: null };
};

const LoginForm = ({ returnUrl }: LoginFormProps) => {
  const [state, formAction, isPending] = useActionState(
    loginAction,
    initialState,
  );

  return (
    <form action={formAction} className="space-y-5">
      <input name="returnUrl" type="hidden" value={returnUrl} />
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700" htmlFor="username">
          账号
        </label>
        <input
          autoComplete="username"
          className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-gray-900 outline-none ring-indigo-200 transition focus:ring-2"
          id="username"
          name="username"
          placeholder="请输入账号"
          required
          type="text"
        />
      </div>
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700" htmlFor="password">
          密码
        </label>
        <input
          autoComplete="current-password"
          className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-gray-900 outline-none ring-indigo-200 transition focus:ring-2"
          id="password"
          name="password"
          placeholder="请输入密码"
          required
          type="password"
        />
      </div>
      {state.error ? (
        <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">
          {state.error}
        </p>
      ) : null}
      <button
        className="w-full rounded-full bg-indigo-600 px-5 py-3 font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-70"
        disabled={isPending}
        type="submit"
      >
        {isPending ? '登录中...' : '登录并进入创作台'}
      </button>
    </form>
  );
};

export default LoginForm;
