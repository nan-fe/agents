import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '小红书内容分享',
  description: '查看 AI 生成的小红书图文内容',
};

const RootLayout = ({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) => {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-pink-50 text-gray-800 antialiased">
        {children}
      </body>
    </html>
  );
};

export default RootLayout;
