'use client';

import * as Sentry from '@sentry/nextjs';
import Link from 'next/link';
import { useEffect } from 'react';

type ShareErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

const ShareError = ({ error, reset }: ShareErrorProps) => {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  console.error('Failed to render share page:', error);

  return (
    <main
      id="main-content"
      className="mx-auto flex min-h-screen w-full max-w-5xl items-center px-4 py-12"
    >
      <section className="atelier-panel w-full p-8 text-center sm:p-12">
        <div className="atelier-panel-inner">
          <p className="atelier-eyebrow">Share Load Failed</p>
          <h1 className="atelier-heading mt-4 text-3xl sm:text-5xl">
            分享内容暂时无法加载
          </h1>
          <p className="atelier-body mx-auto mt-6 max-w-2xl">
            服务可能正在繁忙或网络连接异常，请稍后重试。
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <button className="atelier-btn-primary" type="button" onClick={reset}>
              重新加载
            </button>
            <Link className="atelier-btn-ghost" href="/">
              返回首页
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
};

export default ShareError;
