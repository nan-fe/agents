import Link from 'next/link';

import LoginForm from './login-form';

type LoginPageProps = {
  searchParams: Promise<{
    returnUrl?: string;
  }>;
};

const LoginPage = async ({ searchParams }: LoginPageProps) => {
  const params = await searchParams;
  const returnUrl = params.returnUrl || '/studio';

  return (
    <main
      id="main-content"
      className="flex min-h-screen items-center justify-center px-4 py-12"
    >
      <section className="atelier-panel w-full max-w-md shrink-0 p-8 sm:p-10">
        <span className="atelier-corner-fan" aria-hidden />
        <span className="atelier-corner-fan atelier-corner-fan--bl" aria-hidden />
        <div className="atelier-panel-inner">
          <p className="atelier-eyebrow">Content Atelier</p>
          <h1 className="atelier-heading mt-3 text-3xl">登录创作画室</h1>
          <p className="atelier-body mt-4 text-sm">
            登录后可进入多智能体写作台，开始生成小红书文案与配图。
          </p>
          <div className="mt-8">
            <LoginForm returnUrl={returnUrl} />
          </div>
          <p className="mt-8 text-center font-body text-sm text-ink-muted">
            还没有账号？
            <Link
              className="ml-1 text-burgundy-dark underline-offset-4 hover:underline"
              href="/register"
            >
              立即注册
            </Link>
            <span className="mx-2 text-gold">◆</span>
            <Link
              className="text-burgundy-dark underline-offset-4 hover:underline"
              href="/"
            >
              返回门户首页
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
};

export default LoginPage;
