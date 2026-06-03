import Link from 'next/link';

import { auth } from '@/auth';

const features = [
  {
    title: '多智能体协作',
    description:
      '编排、内容策划、文案、配图、审核等模块协同，完成小红书内容的规划、创作与质检。',
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
    <main
      id="main-content"
      className="mx-auto min-h-screen w-full max-w-6xl px-4 py-12 sm:py-16"
    >
      <section className="atelier-panel p-8 sm:p-12">
        <span className="atelier-corner-fan" aria-hidden />
        <span className="atelier-corner-fan atelier-corner-fan--tr" aria-hidden />
        <div className="atelier-panel-inner">
          <p className="atelier-eyebrow" translate="no">
            XHS Multi-Agent Creator
          </p>
          <h1 className="atelier-heading mt-4 max-w-3xl text-3xl sm:text-5xl">
            小红书内容创作平台
          </h1>
          <div className="atelier-deco-rule my-8">
            <span>Atelier</span>
          </div>
          <p className="atelier-body max-w-3xl text-base sm:text-lg">
            通过编排、内容策划、文案、配图、审核等专业能力协同，自动完成小红书内容的规划、创作、配图和审核全流程。
          </p>
          <div className="mt-10 flex flex-wrap gap-3">
            {loggedInUser ? (
              <Link className="atelier-btn-primary" href="/studio">
                进入创作画室
              </Link>
            ) : (
              <>
                <Link className="atelier-btn-primary" href="/register">
                  注册并开始创作
                </Link>
                <Link className="atelier-btn-ghost" href="/login">
                  登录
                </Link>
              </>
            )}
            <Link className="atelier-btn-ghost" href="/share/demo">
              查看分享页示例
            </Link>
          </div>
          {loggedInUser ? (
            <p className="mt-5 font-body text-sm italic text-ink-muted">
              当前登录账号：
              {loggedInUser.username || loggedInUser.name || '已登录用户'}
            </p>
          ) : null}
        </div>
      </section>

      <section className="mt-10 grid gap-5 md:grid-cols-3">
        {features.map((feature, index) => (
          <article
            className="atelier-panel p-6"
            key={feature.title}
            style={{ animationDelay: `${index * 0.12}s` }}
          >
            <div className="atelier-panel-inner">
              <h2 className="atelier-heading text-lg">{feature.title}</h2>
              <p className="atelier-body mt-3 text-sm">{feature.description}</p>
            </div>
          </article>
        ))}
      </section>
    </main>
  );
};

export default HomePage;
