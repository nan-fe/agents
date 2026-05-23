'use client';

import { useActionState, useEffect, useRef } from 'react';
import { signIn } from 'next-auth/react';
import { useRouter } from 'next/navigation';

import {
  registerAction,
  type RegisterActionState,
} from '@/lib/actions/register-action';

const initialState: RegisterActionState = { error: null, success: false };

const inputClassName =
  'w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-gray-900 outline-none ring-indigo-200 transition focus:ring-2';

type RegisterFormProps = {
  returnUrl: string;
};

const RegisterForm = ({ returnUrl }: RegisterFormProps) => {
  const router = useRouter();
  const pendingCredentials = useRef<{ username: string; password: string } | null>(
    null,
  );
  const [state, formAction, isPending] = useActionState(
    async (prevState: RegisterActionState, formData: FormData) => {
      pendingCredentials.current = {
        username: String(formData.get('username') ?? '').trim(),
        password: String(formData.get('password') ?? ''),
      };
      return registerAction(prevState, formData);
    },
    initialState,
  );

  useEffect(() => {
    if (!state.success || !pendingCredentials.current) {
      return;
    }

    const completeRegistration = async () => {
      const { username, password } = pendingCredentials.current!;

      const result = await signIn('credentials', {
        username,
        password,
        redirect: false,
      });

      if (result?.error) {
        router.push(`/login?returnUrl=${encodeURIComponent(returnUrl)}`);
        return;
      }

      window.location.assign(returnUrl);
    };

    void completeRegistration();
  }, [router, returnUrl, state.success]);

  return (
    <form action={formAction} className="space-y-5">
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700" htmlFor="username">
          账号
        </label>
        <input
          autoComplete="username"
          className={inputClassName}
          id="username"
          name="username"
          placeholder="3–32 位字母、数字或下划线"
          required
          type="text"
        />
      </div>
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700" htmlFor="name">
          昵称（可选）
        </label>
        <input
          autoComplete="name"
          className={inputClassName}
          id="name"
          name="name"
          placeholder="用于界面展示"
          type="text"
        />
      </div>
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700" htmlFor="password">
          密码
        </label>
        <input
          autoComplete="new-password"
          className={inputClassName}
          id="password"
          name="password"
          placeholder="至少 6 位"
          required
          type="password"
        />
      </div>
      <div className="space-y-2">
        <label
          className="block text-sm font-medium text-gray-700"
          htmlFor="confirmPassword"
        >
          确认密码
        </label>
        <input
          autoComplete="new-password"
          className={inputClassName}
          id="confirmPassword"
          name="confirmPassword"
          placeholder="再次输入密码"
          required
          type="password"
        />
      </div>
      {state.error ? (
        <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">
          {state.error}
        </p>
      ) : null}
      {state.success ? (
        <p className="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          注册成功，正在登录...
        </p>
      ) : null}
      <button
        className="w-full rounded-full bg-indigo-600 px-5 py-3 font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-70"
        disabled={isPending || state.success}
        type="submit"
      >
        {isPending ? '注册中...' : '注册并进入创作台'}
      </button>
    </form>
  );
};

export default RegisterForm;
