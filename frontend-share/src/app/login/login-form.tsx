'use client';

import { useActionState } from 'react';
import { signIn } from 'next-auth/react';

import OAuthSignInButtons from '@/components/oauth-sign-in-buttons';
import type { OAuthProviderId } from '@/lib/oauth-providers';

type LoginState = {
  error: string | null;
};

const initialState: LoginState = { error: null };

type LoginFormProps = {
  returnUrl: string;
  oauthProviders: OAuthProviderId[];
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

const LoginForm = ({ returnUrl, oauthProviders }: LoginFormProps) => {
  const [state, formAction, isPending] = useActionState(
    loginAction,
    initialState,
  );

  return (
    <div className="space-y-6">
      <OAuthSignInButtons returnUrl={returnUrl} providers={oauthProviders} />
      <form action={formAction} className="space-y-5">
      <input name="returnUrl" type="hidden" value={returnUrl} />
      <div className="space-y-2">
        <label className="atelier-label" htmlFor="username">
          账号
        </label>
        <input
          autoComplete="username"
          autoCapitalize="off"
          spellCheck={false}
          className="atelier-input"
          id="username"
          name="username"
          placeholder="例如：creator_demo…"
          required
          type="text"
        />
      </div>
      <div className="space-y-2">
        <label className="atelier-label" htmlFor="password">
          密码
        </label>
        <input
          autoComplete="current-password"
          className="atelier-input"
          id="password"
          name="password"
          placeholder="请输入密码…"
          required
          type="password"
        />
      </div>
      {state.error ? (
        <p className="atelier-alert-error" role="alert">
          {state.error}
        </p>
      ) : null}
      <button
        className="atelier-btn-primary w-full"
        disabled={isPending}
        type="submit"
      >
        {isPending ? '登录中…' : '登录并进入创作台'}
      </button>
    </form>
    </div>
  );
};

export default LoginForm;
