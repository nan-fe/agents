import Link from 'next/link';

import RegisterForm from './register-form';

type RegisterPageProps = {
  searchParams: Promise<{
    returnUrl?: string;
  }>;
};

const RegisterPage = async ({ searchParams }: RegisterPageProps) => {
  const params = await searchParams;
  const returnUrl = params.returnUrl || '/studio';

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <section className="w-full max-w-md shrink-0 rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="mb-3 text-sm font-bold tracking-widest text-indigo-600">
          XHS MULTI-AGENT CREATOR
        </p>
        <h1 className="text-3xl font-bold text-gray-950">注册账号</h1>
        <p className="mt-3 text-sm leading-7 text-gray-600">
          创建账号后即可进入多智能体写作台，开始生成小红书文案与配图。
        </p>
        <div className="mt-8">
          <RegisterForm returnUrl={returnUrl} />
        </div>
        <p className="mt-6 text-center text-sm text-gray-500">
          已有账号？
          <Link className="ml-1 text-indigo-600 hover:underline" href="/login">
            去登录
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

export default RegisterPage;
