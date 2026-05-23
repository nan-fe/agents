import type { Metadata } from 'next';
import Image from 'next/image';
import { notFound } from 'next/navigation';
import ShareActions from '../../../components/share-actions';
import { getShareSnapshot } from '../../../lib/shares';

type SharePageProps = {
  params: Promise<{
    shareId: string;
  }>;
};

const toDescription = (content: string) => {
  const normalized = content.replace(/\s+/g, ' ').trim();
  return normalized.length > 120
    ? `${normalized.slice(0, 117)}...`
    : normalized;
};

export const generateMetadata = async ({
  params,
}: SharePageProps): Promise<Metadata> => {
  const { shareId } = await params;
  const share = await getShareSnapshot(shareId);

  if (!share) {
    return {
      title: '分享内容不存在',
    };
  }

  const title = share.title || '小红书内容分享';
  const description = toDescription(
    share.content || share.message || '查看 AI 生成的小红书图文内容'
  );
  const images = share.image_url ? [share.image_url] : [];

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      images,
      type: 'article',
    },
    twitter: {
      card: share.image_url ? 'summary_large_image' : 'summary',
      title,
      description,
      images,
    },
  };
};

const SharePage = async ({ params }: SharePageProps) => {
  const { shareId } = await params;
  const share = await getShareSnapshot(shareId);

  if (!share) {
    notFound();
  }

  const title = share.title || '生成结果';
  const content = share.content || share.message || '暂无可展示内容';
  const hashtags = Array.isArray(share.hashtags) ? share.hashtags : [];

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-12 sm:py-16">
      <article className="overflow-hidden rounded-3xl border border-slate-200 bg-white/95">
        <div className="p-6 sm:p-8">
          <p className="mb-3 text-sm font-bold tracking-widest text-indigo-600">
            {shareId === 'demo' ? 'SHARE DEMO' : 'AI GENERATED CONTENT'}
          </p>
          <h1 className="text-3xl font-bold leading-tight text-gray-950 sm:text-5xl">
            {title}
          </h1>
          <div className="mt-6 whitespace-pre-wrap text-base leading-8 text-gray-700 sm:text-lg">
            {content}
          </div>
          {hashtags.length > 0 && (
            <div className="mt-6 flex flex-wrap gap-2.5">
              {hashtags.map((tag) => (
                <span
                  className="rounded-full bg-slate-100 px-3 py-2 text-sm text-slate-700"
                  key={tag}
                >
                  #{tag}
                </span>
              ))}
            </div>
          )}
          <ShareActions title={title} content={content} hashtags={hashtags} />
        </div>
        {share.image_url && (
          <Image
            className="h-auto max-h-[560px] w-full bg-slate-50 object-contain"
            src={share.image_url}
            alt={title}
            width={1024}
            height={1024}
            unoptimized
          />
        )}
      </article>
      <p className="mt-5 text-center text-sm text-gray-500">
        {shareId === 'demo'
          ? '这是分享页示例内容，登录创作台后可生成并分享真实结果'
          : '由 XHS Multi-Agent Creator 生成'}
      </p>
    </main>
  );
};

export default SharePage;
