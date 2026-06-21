'use client';

import { signIn } from 'next-auth/react';

import type { OAuthProviderId } from '@/lib/oauth-providers';

type OAuthSignInButtonsProps = {
  returnUrl: string;
  providers: OAuthProviderId[];
  registerMode?: boolean;
};

const providerLabels: Record<OAuthProviderId, string> = {
  github: 'GitHub',
  google: 'Google',
};

const OAuthSignInButtons = ({
  returnUrl,
  providers,
  registerMode = false,
}: OAuthSignInButtonsProps) => {
  if (providers.length === 0) {
    return null;
  }

  const handleSignIn = (provider: OAuthProviderId) => {
    void signIn(provider, { callbackUrl: returnUrl });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-gold/40" aria-hidden />
        <span className="font-body text-xs tracking-wide text-ink-muted">
          {registerMode ? '或使用第三方账号快速注册' : '或使用第三方账号'}
        </span>
        <span className="h-px flex-1 bg-gold/40" aria-hidden />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {providers.map((provider) => (
          <button
            key={provider}
            className="atelier-btn-ghost w-full"
            type="button"
            onClick={() => handleSignIn(provider)}
          >
            使用 {providerLabels[provider]} {registerMode ? '注册并登录' : '登录'}
          </button>
        ))}
      </div>
    </div>
  );
};

export default OAuthSignInButtons;
