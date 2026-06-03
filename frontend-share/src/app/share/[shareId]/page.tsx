import type { Metadata } from 'next';
import Image from 'next/image';
import { notFound } from 'next/navigation';
import ShareActions from '../../../components/share-actions';
import { DEMO_SHARE_ID } from '../../../lib/demo-share';
import { preloadShareImage } from '../../../lib/preload-share-image';
import { truncateWithEllipsis } from '@/lib/format';
import { getShareSnapshot } from '../../../lib/shares';

type SharePageProps = {
  params: Promise<{
    shareId: string;
  }>;
};

/** 路由段 ISR（须与 shares.ts 中 SHARE_PAGE_REVALIDATE_SECONDS 一致；Next 要求此处为数字字面量） */
export const revalidate = 3600;

/** 构建时未预生成的 shareId，首次请求时按需生成并进入 ISR 缓存 */
export const dynamicParams = true;

export const generateStaticParams = () => [{ shareId: DEMO_SHARE_ID }];

const toDescription = (content: string) => truncateWithEllipsis(content, 120);

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
    share.content || share.message || '查看 AI 生成的小红书图文内容',
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

  if (share.image_url) {
    preloadShareImage(share.image_url);
  }

  return (
    <main
      id="main-content"
      className="mx-auto w-full max-w-5xl px-4 py-12 sm:py-16"
    >
      <article className="atelier-panel overflow-hidden">
        <span className="atelier-corner-fan" aria-hidden />
        <span className="atelier-corner-fan atelier-corner-fan--tr" aria-hidden />
        <div className="atelier-panel-inner p-6 sm:p-10">
          <p className="atelier-eyebrow">
            {shareId === 'demo' ? 'Share Demo' : 'AI Generated Content'}
          </p>
          <h1 className="atelier-heading mt-4 text-3xl sm:text-5xl">{title}</h1>
          <div className="atelier-deco-rule my-8">
            <span>Gallery</span>
          </div>
          <div className="atelier-body whitespace-pre-wrap text-base sm:text-lg">
            {content}
          </div>
          {hashtags.length > 0 && (
            <div className="mt-8 flex flex-wrap gap-2">
              {hashtags.map((tag) => (
                <span className="atelier-tag" key={tag}>
                  {tag}
                </span>
              ))}
            </div>
          )}
          <ShareActions title={title} content={content} hashtags={hashtags} />
        </div>
        {share.image_url && (
          <div className="atelier-frame mx-6 mb-6 sm:mx-10 sm:mb-10">
            <Image
              className="h-auto max-h-[560px] w-full bg-canvas object-contain"
              src={share.image_url}
              alt={title}
              width={1024}
              height={1024}
              unoptimized
            />
          </div>
        )}
      </article>
      <p className="mt-6 text-center font-body text-sm italic text-ink-muted">
        {shareId === 'demo'
          ? '这是分享页示例内容，登录创作台后可生成并分享真实结果'
          : '由 XHS Multi-Agent Creator 生成'}
      </p>
    </main>
  );
};

export default SharePage;
