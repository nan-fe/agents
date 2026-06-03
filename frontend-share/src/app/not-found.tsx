import Link from 'next/link';

const NotFound = () => {
  return (
    <main
      id="main-content"
      className="mx-auto flex min-h-screen w-full max-w-5xl items-center px-4 py-12"
    >
      <section className="atelier-panel w-full p-8 text-center sm:p-12">
        <div className="atelier-panel-inner">
          <p className="atelier-eyebrow">Share Not Found</p>
          <h1 className="atelier-heading mt-4 text-3xl sm:text-5xl">
            分享内容不存在或已过期
          </h1>
          <p className="atelier-body mx-auto mt-6 max-w-2xl">
            请确认分享链接是否完整，或回到创作端重新生成分享链接。
          </p>
          <div className="mt-8">
            <Link className="atelier-btn-primary" href="/">
              返回首页
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
};

export default NotFound;
