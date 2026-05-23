import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'XHS Multi-Agent Creator',
  description: '基于多智能体的小红书内容创作平台',
};

const RootLayout = ({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) => {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-slate-50 text-gray-800 antialiased">
        {children}
      </body>
    </html>
  );
};

export default RootLayout;
