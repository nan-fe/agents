import type { Metadata } from 'next';
import { Cinzel, Cormorant_Garamond } from 'next/font/google';

import { ResourceHints } from '@/components/resource-hints';
import './globals.css';

const cinzel = Cinzel({
  subsets: ['latin'],
  variable: '--font-display',
  weight: ['500', '600', '700'],
  display: 'swap',
});

const cormorant = Cormorant_Garamond({
  subsets: ['latin'],
  variable: '--font-body',
  weight: ['400', '500', '600', '700'],
  style: ['normal', 'italic'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: '内容创作画室 · XHS Multi-Agent Creator',
  description: '基于多智能体的小红书内容创作平台',
};

const RootLayout = ({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) => {
  return (
    <html
      className={`${cinzel.variable} ${cormorant.variable}`}
      lang="zh-CN"
    >
      <head>
        <ResourceHints />
      </head>
      <body
        className={`${cormorant.className} atelier-canvas atelier-vignette min-h-screen text-ink antialiased`}
      >
        <a className="skip-link" href="#main-content">
          跳到主要内容
        </a>
        {children}
      </body>
    </html>
  );
};

export default RootLayout;
