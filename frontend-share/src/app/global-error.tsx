'use client';

import * as Sentry from '@sentry/nextjs';
import { useEffect } from 'react';

type GlobalErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

const GlobalError = ({ error, reset }: GlobalErrorProps) => {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="zh-CN">
      <body className="flex min-h-screen items-center justify-center bg-slate-50 px-4 text-gray-800">
        <main className="w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-8 text-center">
          <p className="mb-3 text-sm font-bold tracking-widest text-indigo-600">
            APPLICATION ERROR
          </p>
          <h1 className="text-2xl font-bold text-gray-950">页面出现异常</h1>
          <p className="mt-4 text-base leading-7 text-gray-600">
            我们已记录该错误，请稍后重试。
          </p>
          <button
            className="mt-6 rounded-full border border-indigo-600 bg-indigo-600 px-5 py-2.5 text-white transition hover:bg-indigo-700"
            type="button"
            onClick={reset}
          >
            重新加载
          </button>
        </main>
      </body>
    </html>
  );
};

export default GlobalError;
