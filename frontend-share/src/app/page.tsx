import Link from 'next/link';

import { auth } from '@/auth';

const features = [
  {
    title: '多智能体协作',
    description:
      'Planner、Copywriter、Image、Reviewer 等 Agent 协同完成策划、创作、配图与审核。',
  },
  {
    title: '多轮对话创作',
    description: '支持连续修改与版本对比，快速迭代小红书风格文案与配图。',
  },
  {
    title: '一键公开分享',
    description: '生成结果可保存快照并分享，便于团队预览与传播。',
  },
];

const HomePage = async () => {
  const session = await auth();
  const loggedInUser = session?.user;

  return (
    <main className="mx-auto min-h-screen w-full max-w-6xl px-4 py-12">
      <section className="rounded-3xl border border-slate-200 bg-white p-8 sm:p-12">
        <p className="mb-3 text-sm font-bold tracking-widest text-indigo-600">
          XHS MULTI-AGENT CREATOR
        </p>
        <h1 className="max-w-3xl text-3xl font-bold leading-tight text-gray-950 sm:text-5xl">
          基于多智能体的小红书内容创作平台
        </h1>
        <p className="mt-6 max-w-3xl text-base leading-8 text-gray-600 sm:text-lg">
          通过 Planner、Copywriter、Image Designer、Reviewer
          等专业 Agent 协同，自动完成小红书内容的策划、创作、配图和审核全流程。
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          {loggedInUser ? (
            <Link
              className="rounded-full bg-indigo-600 px-5 py-2.5 font-medium text-white transition hover:bg-indigo-700"
              href="/studio"
            >
              进入创作台
            </Link>
          ) : (
            <>
              <Link
                className="rounded-full bg-indigo-600 px-5 py-2.5 font-medium text-white transition hover:bg-indigo-700"
                href="/register"
              >
                注册并开始创作
              </Link>
              <Link
                className="rounded-full border border-slate-200 px-5 py-2.5 text-slate-700 transition hover:border-slate-300"
                href="/login"
              >
                登录
              </Link>
            </>
          )}
          <Link
            className="rounded-full border border-slate-200 px-5 py-2.5 text-slate-700 transition hover:border-slate-300"
            href="/share/demo"
          >
            查看分享页示例
          </Link>
        </div>
        {loggedInUser ? (
          <p className="mt-4 text-sm text-gray-500">
            当前登录账号：{loggedInUser.username || loggedInUser.name || '已登录用户'}
          </p>
        ) : null}
      </section>

      <section className="mt-8 grid gap-4 md:grid-cols-3">
        {features.map((feature) => (
          <article
            className="rounded-3xl border border-slate-100 bg-white p-6"
            key={feature.title}
          >
            <h2 className="text-lg font-semibold text-gray-950">{feature.title}</h2>
            <p className="mt-3 text-sm leading-7 text-gray-600">
              {feature.description}
            </p>
          </article>
        ))}
      </section>
    </main>
  );
};

export default HomePage;
