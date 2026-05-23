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
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <section className="w-full max-w-md shrink-0 rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="mb-3 text-sm font-bold tracking-widest text-indigo-600">
          XHS MULTI-AGENT CREATOR
        </p>
        <h1 className="text-3xl font-bold text-gray-950">登录创作平台</h1>
        <p className="mt-3 text-sm leading-7 text-gray-600">
          登录后可进入多智能体写作台，开始生成小红书文案与配图。
        </p>
        <div className="mt-8">
          <LoginForm returnUrl={returnUrl} />
        </div>
        <p className="mt-6 text-center text-sm text-gray-500">
          还没有账号？
          <Link className="ml-1 text-indigo-600 hover:underline" href="/register">
            立即注册
          </Link>
          <span className="mx-1">·</span>
          <Link className="text-indigo-600 hover:underline" href="/">
            返回门户首页
          </Link>
        </p>
      </section>
    </main>
  );
};

export default LoginPage;
