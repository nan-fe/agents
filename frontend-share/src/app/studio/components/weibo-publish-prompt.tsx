"use client";

import { useEffect, useState } from 'react';
import {
  buildShareUrl,
  getPublishJobStatus,
  reportError,
  type PublishJobResponse,
} from '@/services/api';
import type { DialogResultData } from '@/types/conversation';

type WeiboPublishPromptProps = {
  result: DialogResultData;
};

const TERMINAL = new Set(['succeeded', 'failed']);

const WeiboPublishPrompt = ({ result }: WeiboPublishPromptProps) => {
  const meta = result.weibo_publish;
  const [job, setJob] = useState<PublishJobResponse | null>(null);

  useEffect(() => {
    const jobId = meta?.job_id;
    if (!jobId) {
      return undefined;
    }

    let cancelled = false;
    let timer: number | undefined;

    const poll = async () => {
      try {
        const next = await getPublishJobStatus(jobId);
        if (cancelled) {
          return;
        }
        setJob(next);
        if (TERMINAL.has(next.status) && timer !== undefined) {
          window.clearInterval(timer);
        }
      } catch (error) {
        reportError(error, 'weibo/getPublishJobStatus');
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
  }, [meta?.job_id]);

  if (!meta) {
    return null;
  }

  if (!meta.auto_started && !meta.error) {
    return null;
  }

  const shareUrl = meta.share_id ? buildShareUrl(meta.share_id) : null;

  return (
    <div className="mt-3 rounded-sm border border-gold/25 bg-canvas/50 p-3 font-body text-sm text-ink-muted">
      <p className="text-ink">
        {meta.auto_started
          ? '内容已生成，正在通过 browser-use 自动发布到微博…'
          : '微博自动发布'}
      </p>

      {meta.error && (
        <p className="mt-1 text-burgundy-dark">启动失败：{meta.error}</p>
      )}

      {shareUrl && (
        <p className="mt-1 break-all text-xs">
          分享链接：
          <a className="underline" href={shareUrl} target="_blank" rel="noopener noreferrer">
            {shareUrl}
          </a>
        </p>
      )}

      {job && (
        <div className="mt-2 text-xs">
          {job.status === 'running' || job.status === 'pending' ? (
            <p className="italic text-gold-dark">发布进行中…</p>
          ) : null}
          {job.status === 'succeeded' && (
            <p className="text-gold-dark">
              已发布到微博
              {job.post_url ? (
                <>
                  {' '}
                  <a
                    className="underline"
                    href={job.post_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    查看
                  </a>
                </>
              ) : null}
            </p>
          )}
          {job.status === 'failed' && job.error && (
            <p className="text-burgundy-dark">发布失败：{job.error}</p>
          )}
          {job.progress.length > 0 && (
            <ul className="mt-1 list-inside list-disc">
              {job.progress.slice(-5).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

export default WeiboPublishPrompt;
