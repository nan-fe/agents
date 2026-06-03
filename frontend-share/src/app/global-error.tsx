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
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="theme-color" content="#f0e4cc" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600&family=Cormorant+Garamond:wght@400;500&display=swap"
          rel="stylesheet"
        />
        <style>{`
          html { color-scheme: light; }
          body {
            margin: 0;
            font-family: 'Cormorant Garamond', Georgia, serif;
            color: #2a2218;
            background: #f0e4cc;
          }
          .atelier-btn-primary {
            padding: 0.65rem 1.5rem;
            font-family: Cinzel, serif;
            font-size: 0.75rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: #faf3e8;
            background: #8a6b1f;
            border: 1px solid #e8d48b;
            cursor: pointer;
          }
          .atelier-btn-primary:focus-visible {
            outline: 2px solid #c9a227;
            outline-offset: 2px;
          }
        `}</style>
      </head>
      <body className="flex min-h-screen items-center justify-center px-4">
        <main className="w-full max-w-lg rounded-sm border-2 border-[#c9a227] bg-[#faf3e8] p-8 text-center">
          <p
            style={{
              fontFamily: 'Cinzel, serif',
              fontSize: '0.7rem',
              letterSpacing: '0.32em',
              textTransform: 'uppercase',
              color: '#8a6b1f',
            }}
          >
            Application Error
          </p>
          <h1
            style={{
              fontFamily: 'Cinzel, serif',
              fontSize: '1.5rem',
              marginTop: '1rem',
            }}
          >
            页面出现异常
          </h1>
          <p style={{ marginTop: '1rem', lineHeight: 1.75 }}>
            我们已记录该错误，请稍后重试。
          </p>
          <button className="atelier-btn-primary" type="button" onClick={reset}>
            重新加载
          </button>
        </main>
      </body>
    </html>
  );
};

export default GlobalError;
