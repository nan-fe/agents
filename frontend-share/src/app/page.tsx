import Link from 'next/link';

const HomePage = () => {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl items-center px-4 py-12">
      <section className="w-full rounded-3xl border border-pink-200 bg-white p-8 text-center">
        <p className="mb-3 text-sm font-bold tracking-widest text-pink-600">
          XHS MULTI-AGENT CREATOR
        </p>
        <h1 className="text-3xl font-bold leading-tight text-gray-950 sm:text-5xl">
          分享页已就绪
        </h1>
        <p className="mx-auto mt-6 max-w-2xl whitespace-pre-wrap text-base leading-8 text-gray-600 sm:text-lg">
          请从创作端生成分享链接后访问，链接格式为 /share/[shareId]。
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <Link
            className="rounded-full border border-pink-600 bg-pink-600 px-5 py-2.5 text-white"
            href="/share/demo"
          >
            查看链接格式
          </Link>
        </div>
      </section>
    </main>
  );
};

export default HomePage;
