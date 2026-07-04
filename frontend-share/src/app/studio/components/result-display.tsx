"use client";
import { useCallback, useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
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

const WeiboShareSyncModal = dynamic(() => import('./weibo-share-sync-modal'), {
  ssr: false,
});

const WeiboLoginPanel = dynamic(() => import('./weibo-login-panel'), {
  ssr: false,
});

const isWeiboReady = (status: SocialStatusResponse | null): boolean =>
  Boolean(status?.dry_run) ||
  Boolean(status?.weibo.configured && status?.weibo.logged_in);

type ResultDisplayProps = {
  result?: ShareResult;
  variant?: 'default' | 'minimal';
};

const TERMINAL_JOB_STATUSES = new Set(['succeeded', 'failed']);

const copyTextFallback = (text: string): boolean => {
  try {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-9999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    const copied = document.execCommand('copy');
    document.body.removeChild(textArea);
    return copied;
  } catch {
    return false;
  }
};

/** Best-effort copy; returns false when clipboard is unavailable (e.g. tab unfocused). */
const copyText = async (text: string): Promise<boolean> => {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Long async flows (Weibo publish) often leave the document unfocused.
    }
  }
  return copyTextFallback(text);
};

const pollPublishJob = async (
  jobId: string,
  onUpdate: (job: PublishJobResponse) => void,
): Promise<PublishJobResponse> => {
  for (;;) {
    const job = await getPublishJobStatus(jobId);
    onUpdate(job);
    if (TERMINAL_JOB_STATUSES.has(job.status)) {
      return job;
    }
    await new Promise((resolve) => {
      window.setTimeout(resolve, 2000);
    });
  }
};

const resolvePublishJob = async (
  result: ShareResult,
  onUpdate: (job: PublishJobResponse) => void,
): Promise<PublishJobResponse> => {
  const existingJobId = result.weibo_publish?.job_id?.trim();
  if (existingJobId) {
    const current = await getPublishJobStatus(existingJobId);
    onUpdate(current);
    if (current.status === 'pending' || current.status === 'running') {
      return pollPublishJob(existingJobId, onUpdate);
    }
    if (current.status === 'succeeded') {
      return current;
    }
  }

  const publishResp = await publishToWeibo({
    title: result.title,
    content: result.content,
    hashtags: result.hashtags,
    image_url: result.image_url,
    review_approved: result.review_approved,
    version_id: result.version_id,
  });
  return pollPublishJob(publishResp.job_id, onUpdate);
};

const ResultDisplay = ({ result, variant = 'default' }: ResultDisplayProps) => {
  const { message } = App.useApp();
  const [socialStatus, setSocialStatus] = useState<SocialStatusResponse | null>(null);
  const [shareUrl, setShareUrl] = useState('');
  const [publishJobId, setPublishJobId] = useState('');
  const [publishJob, setPublishJob] = useState<PublishJobResponse | null>(null);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [isWorking, setIsWorking] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalPhase, setModalPhase] = useState<'confirm' | 'publishing'>('confirm');
  const [modalPublishJob, setModalPublishJob] = useState<PublishJobResponse | null>(null);
  const [loginOpen, setLoginOpen] = useState(false);
  const publishAfterLoginRef = useRef(false);

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
        setSocialStatus({
          weibo_publish_enabled: false,
          weibo: { configured: false, logged_in: false },
          x_sync_enabled: false,
          x_sync_interval_seconds: 300,
          review_required: true,
          auto_on_complete: false,
          publish_engine: 'browser_use',
          dry_run: false,
        });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const jobId = publishJobId;
    if (!jobId || modalOpen) {
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
  }, [publishJobId, modalOpen]);

  const finalizeShare = useCallback(
    async (shareResult: ShareResult) => {
      const existingShareId = shareResult.weibo_publish?.share_id;
      let url: string;
      if (existingShareId) {
        url = buildShareUrl(existingShareId);
        setPublishJobId(shareResult.weibo_publish?.job_id ?? '');
      } else {
        const response = await createShare(shareResult);
        url = buildShareUrl(response.share_id);
      }

      setShareUrl(url);
      const copied = await copyText(url);
      if (copied) {
        message.success(
          existingShareId ? '分享链接已复制' : '分享链接已生成并复制',
        );
      } else {
        message.success(
          existingShareId ? '分享链接已就绪' : '分享链接已生成',
        );
        message.info('自动复制失败，请点击下方「复制链接」');
      }
      return url;
    },
    [message],
  );

  const createShareOnly = useCallback(async () => {
    if (!result) {
      return;
    }
    setIsWorking(true);
    try {
      await finalizeShare(result);
    } catch (error) {
      console.error('创建分享链接失败:', error);
      reportError(error, 'result/createShare');
      message.error('创建分享链接失败，请稍后重试');
    } finally {
      setIsWorking(false);
    }
  }, [finalizeShare, message, result]);

  const publishThenShare = useCallback(async () => {
    if (!result) {
      return;
    }

    setModalPhase('publishing');
    setModalPublishJob(null);
    setPublishError(null);

    try {
      const job = await resolvePublishJob(result, setModalPublishJob);
      setPublishJobId(job.job_id);
      setPublishJob(job);
      setModalPublishJob(job);

      if (job.status === 'succeeded') {
        message.success('已成功发布到微博');
      } else if (job.error) {
        setPublishError(job.error);
        message.error(`微博发布失败：${job.error}`);
      }
    } catch (error) {
      const detail =
        error instanceof Error ? error.message : '微博发布失败';
      setPublishError(detail);
      reportError(error, 'result/publishToWeibo');
      message.error(detail);
    }

    try {
      await finalizeShare(result);
    } catch (error) {
      console.error('创建分享链接失败:', error);
      reportError(error, 'result/createShare');
      message.error('创建分享链接失败，请稍后重试');
    } finally {
      setModalOpen(false);
      setModalPhase('confirm');
      setModalPublishJob(null);
      setIsWorking(false);
    }
  }, [finalizeShare, message, result]);

  const canPromptWeibo =
    Boolean(socialStatus?.weibo_publish_enabled) &&
    (!socialStatus?.review_required || result?.review_approved === true);

  const handleConfirmWeiboPublish = () => {
    if (!isWeiboReady(socialStatus)) {
      publishAfterLoginRef.current = true;
      setModalOpen(false);
      setLoginOpen(true);
      return;
    }
    setIsWorking(true);
    void publishThenShare();
  };

  const copyExistingShare = useCallback(async () => {
    if (!result) {
      return;
    }
    const existingShareId = result.weibo_publish?.share_id;
    if (!existingShareId) {
      return;
    }
    setIsWorking(true);
    try {
      const url = buildShareUrl(existingShareId);
      setShareUrl(url);
      setPublishJobId(result.weibo_publish?.job_id ?? '');
      const copied = await copyText(url);
      message.success(copied ? '分享链接已复制' : '分享链接已就绪');
      if (!copied) {
        message.info('自动复制失败，请点击下方「复制链接」');
      }
    } finally {
      setIsWorking(false);
    }
  }, [message, result]);

  const handleGenerateClick = () => {
    if (!result) {
      return;
    }

    if (canPromptWeibo) {
      setModalPhase('confirm');
      setModalOpen(true);
      return;
    }

    const existingShareId = result.weibo_publish?.share_id;
    if (existingShareId) {
      void copyExistingShare();
      return;
    }

    if (
      socialStatus?.weibo_publish_enabled &&
      socialStatus.review_required &&
      result.review_approved !== true
    ) {
      message.warning('内容尚未审核通过，仅生成分享链接');
    }

    void createShareOnly();
  };

  const isMinimal = variant === 'minimal';
  const title = result?.title || '生成结果';
  const content = result?.content || result?.message || '暂无可展示内容';
  const resultHashtags = result?.hashtags;
  const hashtags: string[] = Array.isArray(resultHashtags) ? resultHashtags : [];
  const isPublishing =
    Boolean(publishJobId) &&
    publishJob !== null &&
    !TERMINAL_JOB_STATUSES.has(publishJob.status);

  if (!result) {
    return null;
  }

  const shareButtonLabel = shareUrl ? '复制分享链接' : '生成分享链接';

  return (
    <>
      <WeiboLoginPanel
        open={loginOpen}
        onClose={() => {
          publishAfterLoginRef.current = false;
          setLoginOpen(false);
        }}
        onLoggedIn={() => {
          void getSocialStatus(true)
            .then((status) => {
              setSocialStatus(status);
              if (publishAfterLoginRef.current && isWeiboReady(status)) {
                publishAfterLoginRef.current = false;
                setIsWorking(true);
                void publishThenShare();
              }
            })
            .catch((error) => {
              reportError(error, 'result/getSocialStatus');
            });
        }}
      />

      {modalOpen && (
        <WeiboShareSyncModal
          open={modalOpen}
          phase={modalPhase}
          publishJob={modalPublishJob}
          onConfirm={handleConfirmWeiboPublish}
          onShareOnly={() => {
            setModalOpen(false);
            void createShareOnly();
          }}
          onCancel={() => {
            if (modalPhase === 'publishing') {
              return;
            }
            setModalOpen(false);
          }}
        />
      )}

      <div
        className={`font-body ${isMinimal ? 'result-display--minimal' : 'result-display'}`}
      >
        <p aria-live="polite" className="sr-only">
          {shareUrl ? '分享链接已生成并复制到剪贴板' : ''}
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
            loading={isWorking || isPublishing}
            disabled={socialStatus === null}
            className={
              isMinimal
                ? '!h-auto !p-0 !font-body !text-sm !italic !text-gold-dark hover:!text-burgundy-dark'
                : '!font-display !text-xs !uppercase !tracking-widest'
            }
            onClick={handleGenerateClick}
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

        {shareUrl && (
          <div className={isMinimal ? 'result-display__share' : 'mt-4 border border-gold/40 bg-canvas/80 p-4 text-sm text-ink-muted'}>
            {!isMinimal && (
              <div className="mb-2 font-display text-xs font-semibold uppercase tracking-widest text-gold-dark">
                分享链接已生成
              </div>
            )}
            <p className="break-all font-body text-sm text-ink-muted">{shareUrl}</p>
            <div className="mt-2 flex flex-wrap gap-3">
              <button
                className="result-display__link-btn"
                type="button"
                onClick={() => {
                  void copyText(shareUrl).then((copied) => {
                    if (copied) {
                      message.success('已复制到剪贴板');
                    } else {
                      message.warning('复制失败，请手动选中链接');
                    }
                  });
                }}
              >
                复制链接
              </button>
              <a
                className="result-display__link-btn"
                href={shareUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                打开分享页
              </a>
            </div>

            {publishError && (
              <p className="mt-2 font-body text-sm text-burgundy-dark">
                微博发布失败：{publishError}
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
    </>
  );
};

export default ResultDisplay;
