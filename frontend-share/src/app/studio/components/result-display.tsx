"use client";
import { startTransition, useActionState, useEffect, useState } from 'react';
import { Button, App } from 'antd';
import ReactMarkdown from 'react-markdown';
import {
  buildShareUrl,
  createShare,
  getPublishJobStatus,
  getSocialStatus,
  publishToWeibo,
  reportError,
  type PublishJobResponse,
  type ShareResult,
  type SocialStatusResponse,
} from '@/services/api';

type ShareActionState = {
  shareUrl: string;
  publishJobId: string;
  publishError: string | null;
};

type ResultDisplayProps = {
  result?: ShareResult;
  variant?: 'default' | 'minimal';
};

const initialShareState: ShareActionState = {
  shareUrl: '',
  publishJobId: '',
  publishError: null,
};

const TERMINAL_JOB_STATUSES = new Set(['succeeded', 'failed']);

const copyText = async (text: string) => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textArea = document.createElement('textarea');
  textArea.value = text;
  textArea.style.position = 'fixed';
  textArea.style.left = '-9999px';
  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();
  document.execCommand('copy');
  document.body.removeChild(textArea);
};

const shareResultAction = (
  messageApi: ReturnType<typeof App.useApp>['message'],
  socialStatus: SocialStatusResponse | null,
) => async (
  prevState: ShareActionState,
  shareResult: ShareResult,
): Promise<ShareActionState> => {
  try {
    const existingShareId = shareResult.weibo_publish?.share_id;
    if (existingShareId) {
      const url = buildShareUrl(existingShareId);
      await copyText(url);
      messageApi.success('分享链接已复制');
      return {
        shareUrl: url,
        publishJobId: shareResult.weibo_publish?.job_id ?? '',
        publishError: null,
      };
    }

    const response = await createShare(shareResult);
    const url = buildShareUrl(response.share_id);
    await copyText(url);
    messageApi.success('分享链接已生成并复制');

    const canPublish =
      socialStatus?.weibo_publish_enabled &&
      !shareResult.weibo_publish?.auto_started &&
      (!socialStatus.review_required || shareResult.review_approved === true);

    if (!canPublish) {
      if (socialStatus?.weibo_publish_enabled && socialStatus.review_required && shareResult.review_approved !== true) {
        messageApi.warning('内容尚未审核通过，仅生成分享链接');
      }
      return { shareUrl: url, publishJobId: '', publishError: null };
    }

    try {
      const publishResp = await publishToWeibo({
        title: shareResult.title,
        content: shareResult.content,
        hashtags: shareResult.hashtags,
        image_url: shareResult.image_url,
        share_url: url,
        review_approved: shareResult.review_approved,
        version_id: shareResult.version_id,
      });
      messageApi.info('正在发布到微博…');
      return {
        shareUrl: url,
        publishJobId: publishResp.job_id,
        publishError: null,
      };
    } catch (publishError) {
      const detail =
        publishError instanceof Error
          ? publishError.message
          : '微博发布失败，分享链接仍可用';
      reportError(publishError, 'result/publishToWeibo');
      messageApi.error(detail);
      return { shareUrl: url, publishJobId: '', publishError: detail };
    }
  } catch (error) {
    console.error('创建分享链接失败:', error);
    reportError(error, 'result/createShare');
    messageApi.error('创建分享链接失败，请稍后重试');
    return prevState;
  }
};

const ResultDisplay = ({ result, variant = 'default' }: ResultDisplayProps) => {
  const { message } = App.useApp();
  const [socialStatus, setSocialStatus] = useState<SocialStatusResponse | null>(null);
  const [publishJob, setPublishJob] = useState<PublishJobResponse | null>(null);

  const [shareState, createShareLink, isSharing] = useActionState(
    shareResultAction(message, socialStatus),
    initialShareState,
  );

  useEffect(() => {
    let cancelled = false;
    getSocialStatus()
      .then((status) => {
        if (!cancelled) {
          setSocialStatus(status);
        }
      })
      .catch((error) => {
        reportError(error, 'result/getSocialStatus');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const jobId = shareState.publishJobId;
    if (!jobId) {
      return undefined;
    }

    let cancelled = false;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const job = await getPublishJobStatus(jobId);
        if (cancelled) {
          return;
        }
        setPublishJob(job);
        if (TERMINAL_JOB_STATUSES.has(job.status)) {
          if (timer !== undefined) {
            window.clearInterval(timer);
          }
          if (job.status === 'succeeded') {
            message.success('已成功发布到微博');
          } else if (job.error) {
            message.error(`微博发布失败：${job.error}`);
          }
        }
      } catch (error) {
        reportError(error, 'result/getPublishJobStatus');
      }
    };

    void poll();
    timer = window.setInterval(() => {
      void poll();
    }, 2000);

    return () => {
      cancelled = true;
      if (timer !== undefined) {
        window.clearInterval(timer);
      }
    };
  }, [shareState.publishJobId, message]);

  const isMinimal = variant === 'minimal';
  const title = result?.title || '生成结果';
  const content = result?.content || result?.message || '暂无可展示内容';
  const resultHashtags = result?.hashtags;
  const hashtags: string[] = Array.isArray(resultHashtags) ? resultHashtags : [];
  const isPublishing =
    Boolean(shareState.publishJobId) &&
    publishJob !== null &&
    !TERMINAL_JOB_STATUSES.has(publishJob.status);

  if (!result) {
    return null;
  }

  const shareButtonLabel =
    result?.weibo_publish?.auto_started
      ? '复制分享链接'
      : socialStatus?.weibo_publish_enabled
        ? '分享并发布'
        : '生成分享链接';

  return (
    <div
      className={`font-body ${isMinimal ? 'result-display--minimal' : 'result-display'}`}
    >
      <p aria-live="polite" className="sr-only">
        {shareState.shareUrl ? '分享链接已生成并复制到剪贴板' : ''}
      </p>

      <div className={isMinimal ? 'result-display__head' : 'mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between'}>
        <h3
          className={
            isMinimal
              ? 'result-display__title'
              : 'm-0 font-display text-xl font-semibold tracking-wide text-ink'
          }
        >
          {title}
        </h3>
        <Button
          type={isMinimal ? 'text' : 'primary'}
          loading={isSharing || isPublishing}
          className={
            isMinimal
              ? '!h-auto !p-0 !font-body !text-sm !italic !text-gold-dark hover:!text-burgundy-dark'
              : '!font-display !text-xs !uppercase !tracking-widest'
          }
          onClick={() => {
            startTransition(() => {
              createShareLink(result);
            });
          }}
        >
          {shareButtonLabel}
        </Button>
      </div>

      <div
        className={
          isMinimal
            ? 'result-display__prose text-ink-muted'
            : 'leading-relaxed text-ink-muted [&_p]:font-body [&_p]:text-lg'
        }
      >
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>

      {hashtags.length > 0 && (
        <p className={isMinimal ? 'result-display__tags' : 'mt-4 flex flex-wrap gap-2'}>
          {hashtags.map((tag: string) => (
            <span key={tag} className={isMinimal ? 'result-display__tag' : 'atelier-tag'}>
              {isMinimal ? `#${tag.replace(/^#/, '')}` : tag}
            </span>
          ))}
        </p>
      )}

      {shareState.shareUrl && (
        <div className={isMinimal ? 'result-display__share' : 'mt-4 border border-gold/40 bg-canvas/80 p-4 text-sm text-ink-muted'}>
          {!isMinimal && (
            <div className="mb-2 font-display text-xs font-semibold uppercase tracking-widest text-gold-dark">
              分享链接已生成
            </div>
          )}
          <p className="break-all font-body text-sm text-ink-muted">{shareState.shareUrl}</p>
          <div className="mt-2 flex flex-wrap gap-3">
            <button
              className="result-display__link-btn"
              type="button"
              onClick={() => copyText(shareState.shareUrl)}
            >
              复制链接
            </button>
            <a
              className="result-display__link-btn"
              href={shareState.shareUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              打开分享页
            </a>
          </div>

          {shareState.publishError && (
            <p className="mt-2 font-body text-sm text-burgundy-dark">
              微博发布失败：{shareState.publishError}
            </p>
          )}

          {publishJob && (
            <div className="mt-3 font-body text-sm text-ink-muted">
              {isPublishing && (
                <p className="italic text-gold-dark">正在发布到微博…</p>
              )}
              {publishJob.status === 'succeeded' && (
                <p className="text-gold-dark">
                  已发布到微博
                  {publishJob.post_url ? (
                    <>
                      {' '}
                      <a
                        className="underline"
                        href={publishJob.post_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        查看微博
                      </a>
                    </>
                  ) : null}
                </p>
              )}
              {publishJob.status === 'failed' && publishJob.error && (
                <p className="text-burgundy-dark">微博发布失败：{publishJob.error}</p>
              )}
              {publishJob.progress.length > 0 && (
                <ul className="mt-1 list-inside list-disc text-xs">
                  {publishJob.progress.slice(-4).map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}

      {result.image_url && (
        <figure className={isMinimal ? 'result-display__figure' : 'atelier-frame rounded-sm'}>
          <img
            src={result.image_url}
            alt={title ? `${title} 配图` : '生成的配图'}
            width={1024}
            height={1024}
            loading="lazy"
            className="max-h-96 w-full object-contain"
          />
        </figure>
      )}
    </div>
  );
};

export default ResultDisplay;
