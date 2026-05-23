'use client';

import Link from 'next/link';

type ShareErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

const ShareError = ({ error, reset }: ShareErrorProps) => {
  console.error('Failed to render share page:', error);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl items-center px-4 py-12">
      <section className="w-full rounded-3xl border border-slate-200 bg-white p-8 text-center">
        <p className="mb-3 text-sm font-bold tracking-widest text-indigo-600">
          SHARE LOAD FAILED
        </p>
        <h1 className="text-3xl font-bold leading-tight text-gray-950 sm:text-5xl">
          分享内容暂时无法加载
        </h1>
        <p className="mx-auto mt-6 max-w-2xl whitespace-pre-wrap text-base leading-8 text-gray-600 sm:text-lg">
          服务可能正在繁忙或网络连接异常，请稍后重试。
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <button
            className="rounded-full border border-indigo-600 bg-indigo-600 px-5 py-2.5 text-white transition hover:bg-indigo-700"
            type="button"
            onClick={reset}
          >
            重新加载
          </button>
          <Link
            className="rounded-full border border-slate-300 bg-white px-5 py-2.5 text-slate-700 transition hover:border-slate-400 hover:text-slate-900"
            href="/"
          >
            返回首页
          </Link>
        </div>
      </section>
    </main>
  );
};

export default ShareError;
