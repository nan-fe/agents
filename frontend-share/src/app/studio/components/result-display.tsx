"use client";
import { useCallback, useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { useSession } from 'next-auth/react';
import { Button, App } from 'antd';
import ReactMarkdown from 'react-markdown';
import {
  buildShareUrl,
  createShare,
  getPublishJobStatus,
  getSocialStatus,
  getWeiboOAuthUserStatus,
  getXOAuthUserStatus,
  publishToWeibo,
  publishToX,
  reportError,
  type PublishJobResponse,
  type ShareResult,
  type SocialStatusResponse,
  type WeiboOAuthUserStatus,
  type XOAuthUserStatus,
} from '@/services/api';
import { getStudioUserId } from '@/app/studio/lib/studio-user';
import type { SocialPublishPlatform } from './social-share-sync-modal';

const SocialShareSyncModal = dynamic(() => import('./social-share-sync-modal'), {
  ssr: false,
});

const WeiboOAuthConnectPanel = dynamic(() => import('./weibo-oauth-connect-panel'), {
  ssr: false,
});

const WeiboLoginPanel = dynamic(() => import('./weibo-login-panel'), {
  ssr: false,
});

const XOAuthConnectPanel = dynamic(() => import('./x-oauth-connect-panel'), {
  ssr: false,
});

const XLoginPanel = dynamic(() => import('./x-login-panel'), {
  ssr: false,
});

const isWeiboReady = (
  status: SocialStatusResponse | null,
  oauthStatus: WeiboOAuthUserStatus | null,
): boolean =>
  Boolean(status?.dry_run) ||
  Boolean(
    status?.weibo_oauth_configured
      ? oauthStatus?.connected
      : status?.weibo.configured && status?.weibo.logged_in || oauthStatus?.connected,
  );

const isXReady = (
  status: SocialStatusResponse | null,
  oauthStatus: XOAuthUserStatus | null,
): boolean =>
  Boolean(status?.x_dry_run) ||
  Boolean(
    status?.x_oauth_configured
      ? oauthStatus?.connected
      : status?.x?.logged_in || oauthStatus?.connected,
  );

const canPromptWeibo = (
  status: SocialStatusResponse,
  result: ShareResult,
): boolean =>
  Boolean(status.weibo_publish_enabled) &&
  (!status.review_required || result.review_approved === true);

const canPromptX = (
  status: SocialStatusResponse,
  result: ShareResult,
): boolean =>
  Boolean(status.x_publish_enabled) &&
  (!status.x_review_required || result.review_approved === true);

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
  platform: SocialPublishPlatform,
  userId: string,
  onUpdate: (job: PublishJobResponse) => void,
): Promise<PublishJobResponse> => {
  const existingJobId = result.weibo_publish?.job_id?.trim();
  if (platform === 'weibo' && existingJobId) {
    const current = await getPublishJobStatus(existingJobId);
    onUpdate(current);
    if (current.status === 'pending' || current.status === 'running') {
      return pollPublishJob(existingJobId, onUpdate);
    }
    if (current.status === 'succeeded') {
      return current;
    }
  }

  const publishResp =
    platform === 'x'
      ? await publishToX({
          user_id: userId,
          title: result.title,
          content: result.content,
          hashtags: result.hashtags,
          image_url: result.image_url,
          review_approved: result.review_approved,
          version_id: result.version_id,
        })
      : await publishToWeibo({
          user_id: userId,
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
  const { data: session } = useSession();
  const userId = getStudioUserId(session);
  const [socialStatus, setSocialStatus] = useState<SocialStatusResponse | null>(null);
  const [weiboOAuthStatus, setWeiboOAuthStatus] = useState<WeiboOAuthUserStatus | null>(null);
  const [xOAuthStatus, setXOAuthStatus] = useState<XOAuthUserStatus | null>(null);
  const [shareUrl, setShareUrl] = useState('');
  const [publishJobId, setPublishJobId] = useState('');
  const [publishJob, setPublishJob] = useState<PublishJobResponse | null>(null);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [isWorking, setIsWorking] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalPhase, setModalPhase] = useState<'choose' | 'confirm' | 'publishing'>('confirm');
  const [modalPlatform, setModalPlatform] = useState<SocialPublishPlatform>('weibo');
  const [modalPublishJob, setModalPublishJob] = useState<PublishJobResponse | null>(null);
  const [weiboOAuthOpen, setWeiboOAuthOpen] = useState(false);
  const [weiboLoginOpen, setWeiboLoginOpen] = useState(false);
  const [xOAuthOpen, setXOAuthOpen] = useState(false);
  const [xLoginOpen, setXLoginOpen] = useState(false);
  const publishAfterLoginRef = useRef(false);
  const pendingPlatformRef = useRef<SocialPublishPlatform>('weibo');

  const ensureSocialStatus = useCallback(async (): Promise<SocialStatusResponse> => {
    if (socialStatus) {
      return socialStatus;
    }
    try {
      const status = await getSocialStatus(false, userId || undefined);
      setSocialStatus(status);
      if (userId && status.weibo_publish_enabled) {
        const weiboOauth = await getWeiboOAuthUserStatus(userId);
        setWeiboOAuthStatus(weiboOauth);
      }
      if (userId && status.x_publish_enabled) {
        const oauth = await getXOAuthUserStatus(userId);
        setXOAuthStatus(oauth);
      }
      return status;
    } catch (error) {
      reportError(error, 'result/getSocialStatus');
      const fallback: SocialStatusResponse = {
        weibo_publish_enabled: false,
        weibo: { configured: false, logged_in: false },
        weibo_oauth_configured: false,
        x_publish_enabled: false,
        x: { configured: false, logged_in: false },
        x_oauth_configured: false,
        x_sync_enabled: false,
        x_sync_interval_seconds: 300,
        review_required: true,
        x_review_required: true,
        auto_on_complete: false,
        publish_engine: 'playwright',
        x_publish_engine: 'playwright',
        dry_run: false,
        x_dry_run: false,
      };
      setSocialStatus(fallback);
      return fallback;
    }
  }, [socialStatus, userId]);

  useEffect(() => {
    if (!userId) {
      setXOAuthStatus(null);
      return;
    }
    void getXOAuthUserStatus(userId)
      .then((status) => setXOAuthStatus(status))
      .catch((error) => reportError(error, 'result/getXOAuthUserStatus'));
  }, [userId]);

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
    if (modalPlatform === 'x' && !userId) {
      message.error('请先登录 Studio 账号');
      return;
    }

    setModalPhase('publishing');
    setModalPublishJob(null);
    setPublishError(null);

    try {
      const job = await resolvePublishJob(
        result,
        modalPlatform,
        userId,
        setModalPublishJob,
      );
      setPublishJobId(job.job_id);
      setPublishJob(job);
      setModalPublishJob(job);

      const platformLabel = modalPlatform === 'x' ? 'X' : '微博';
      if (job.status === 'succeeded') {
        message.success(`已成功发布到${platformLabel}`);
      } else if (job.error) {
        setPublishError(job.error);
        message.error(`${platformLabel}发布失败：${job.error}`);
      }
    } catch (error) {
      const platformLabel = modalPlatform === 'x' ? 'X' : '微博';
      const detail =
        error instanceof Error ? error.message : `${platformLabel}发布失败`;
      setPublishError(detail);
      reportError(error, 'result/publishToSocial');
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
  }, [finalizeShare, message, modalPlatform, result, userId]);

  const handleConfirmPublish = () => {
    if (modalPlatform === 'weibo' && !isWeiboReady(socialStatus, weiboOAuthStatus)) {
      publishAfterLoginRef.current = true;
      pendingPlatformRef.current = 'weibo';
      setModalOpen(false);
      if (socialStatus?.weibo_oauth_configured) {
        setWeiboOAuthOpen(true);
      } else {
        setWeiboLoginOpen(true);
      }
      return;
    }
    if (modalPlatform === 'x' && !isXReady(socialStatus, xOAuthStatus)) {
      publishAfterLoginRef.current = true;
      pendingPlatformRef.current = 'x';
      setModalOpen(false);
      if (socialStatus?.x_oauth_configured) {
        setXOAuthOpen(true);
      } else {
        setXLoginOpen(true);
      }
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

    void (async () => {
      const status = await ensureSocialStatus();
      const weiboEligible = canPromptWeibo(status, result);
      const xEligible = canPromptX(status, result);

      if (weiboEligible && xEligible) {
        setModalPhase('choose');
        setModalOpen(true);
        return;
      }

      if (weiboEligible) {
        setModalPlatform('weibo');
        setModalPhase('confirm');
        setModalOpen(true);
        return;
      }

      if (xEligible) {
        setModalPlatform('x');
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
        status.weibo_publish_enabled &&
        status.review_required &&
        result.review_approved !== true
      ) {
        message.warning('内容尚未审核通过，仅生成分享链接');
      }

      void createShareOnly();
    })();
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

  const platformLabel =
    publishJob?.platform === 'x' || modalPlatform === 'x' ? 'X' : '微博';

  return (
    <>
      {userId && (
        <>
          <WeiboOAuthConnectPanel
            open={weiboOAuthOpen}
            userId={userId}
            onClose={() => {
              publishAfterLoginRef.current = false;
              setWeiboOAuthOpen(false);
            }}
            onConnected={() => {
              void getWeiboOAuthUserStatus(userId, true)
                .then(async (oauth) => {
                  setWeiboOAuthStatus(oauth);
                  const status = await getSocialStatus(true, userId);
                  setSocialStatus(status);
                  if (
                    publishAfterLoginRef.current &&
                    pendingPlatformRef.current === 'weibo' &&
                    isWeiboReady(status, oauth)
                  ) {
                    publishAfterLoginRef.current = false;
                    setModalPlatform('weibo');
                    setModalPhase('confirm');
                    setModalOpen(true);
                  }
                })
                .catch((error) => {
                  reportError(error, 'result/getWeiboOAuthUserStatus');
                });
            }}
          />
          <WeiboLoginPanel
            open={weiboLoginOpen}
            userId={userId}
            onClose={() => {
              publishAfterLoginRef.current = false;
              setWeiboLoginOpen(false);
            }}
            onLoggedIn={() => {
              void getSocialStatus(true, userId)
                .then((status) => {
                  setSocialStatus(status);
                  return getWeiboOAuthUserStatus(userId, true);
                })
                .then((oauth) => {
                  setWeiboOAuthStatus(oauth);
                  if (
                    publishAfterLoginRef.current &&
                    pendingPlatformRef.current === 'weibo' &&
                    isWeiboReady(socialStatus, oauth)
                  ) {
                    publishAfterLoginRef.current = false;
                    setModalPlatform('weibo');
                    setModalPhase('confirm');
                    setModalOpen(true);
                  }
                })
                .catch((error) => {
                  reportError(error, 'result/getSocialStatus');
                });
            }}
          />
          <XOAuthConnectPanel
            open={xOAuthOpen}
            userId={userId}
            onClose={() => {
              publishAfterLoginRef.current = false;
              setXOAuthOpen(false);
            }}
            onConnected={() => {
              void getXOAuthUserStatus(userId, true)
                .then(async (oauth) => {
                  setXOAuthStatus(oauth);
                  const status = await getSocialStatus(true, userId);
                  setSocialStatus(status);
                  if (
                    publishAfterLoginRef.current &&
                    pendingPlatformRef.current === 'x' &&
                    isXReady(status, oauth)
                  ) {
                    publishAfterLoginRef.current = false;
                    setModalPlatform('x');
                    setModalPhase('confirm');
                    setModalOpen(true);
                  }
                })
                .catch((error) => {
                  reportError(error, 'result/getXOAuthUserStatus');
                });
            }}
          />
          <XLoginPanel
            open={xLoginOpen}
            userId={userId}
            onClose={() => {
              publishAfterLoginRef.current = false;
              setXLoginOpen(false);
            }}
            onLoggedIn={() => {
              void getSocialStatus(true, userId)
                .then((status) => {
                  setSocialStatus(status);
                  return getXOAuthUserStatus(userId, true);
                })
                .then((oauth) => {
                  setXOAuthStatus(oauth);
                  if (
                    publishAfterLoginRef.current &&
                    pendingPlatformRef.current === 'x' &&
                    isXReady(socialStatus, oauth)
                  ) {
                    publishAfterLoginRef.current = false;
                    setModalPlatform('x');
                    setModalPhase('confirm');
                    setModalOpen(true);
                  }
                })
                .catch((error) => {
                  reportError(error, 'result/getSocialStatus');
                });
            }}
          />
        </>
      )}

      {modalOpen && (
        <SocialShareSyncModal
          open={modalOpen}
          phase={modalPhase}
          platform={modalPlatform}
          publishJob={modalPublishJob}
          showWeibo={Boolean(socialStatus?.weibo_publish_enabled)}
          showX={Boolean(socialStatus?.x_publish_enabled)}
          onSelectPlatform={(platform) => {
            setModalPlatform(platform);
            setModalPhase('confirm');
          }}
          onConfirm={handleConfirmPublish}
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
                {platformLabel}发布失败：{publishError}
              </p>
            )}

            {publishJob && (
              <div className="mt-3 font-body text-sm text-ink-muted">
                {isPublishing && (
                  <p className="italic text-gold-dark">正在发布到{platformLabel}…</p>
                )}
                {publishJob.status === 'succeeded' && (
                  <p className="text-gold-dark">
                    已发布到{platformLabel}
                    {publishJob.post_url ? (
                      <>
                        {' '}
                        <a
                          className="underline"
                          href={publishJob.post_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          查看帖子
                        </a>
                      </>
                    ) : null}
                  </p>
                )}
                {publishJob.status === 'failed' && publishJob.error && (
                  <p className="text-burgundy-dark">
                    {platformLabel}发布失败：{publishJob.error}
                  </p>
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
