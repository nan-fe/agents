import Link from 'next/link';

const NotFound = () => {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl items-center px-4 py-12">
      <section className="w-full rounded-3xl border border-pink-200 bg-white p-8 text-center">
        <p className="mb-3 text-sm font-bold tracking-widest text-pink-600">
          SHARE NOT FOUND
        </p>
        <h1 className="text-3xl font-bold leading-tight text-gray-950 sm:text-5xl">
          分享内容不存在或已过期
        </h1>
        <p className="mx-auto mt-6 max-w-2xl whitespace-pre-wrap text-base leading-8 text-gray-600 sm:text-lg">
          请确认分享链接是否完整，或回到创作端重新生成分享链接。
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <Link
            className="rounded-full border border-pink-600 bg-pink-600 px-5 py-2.5 text-white"
            href="/"
          >
            返回首页
          </Link>
        </div>
      </section>
    </main>
  );
};

export default NotFound;
