import { startTransition, useActionState } from 'react';
import { Button, message } from 'antd';
import ReactMarkdown from 'react-markdown';
import {
  buildShareUrl,
  createShare,
  reportError,
  type ShareResult,
} from '../services/api';

type ShareActionState = {
  shareUrl: string;
};

type ResultDisplayProps = {
  result?: ShareResult;
  variant?: 'default' | 'minimal';
};

const initialShareState: ShareActionState = { shareUrl: '' };

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

const shareResultAction = async (
  prevState: ShareActionState,
  shareResult: ShareResult,
): Promise<ShareActionState> => {
  try {
    const response = await createShare(shareResult);
    const url = buildShareUrl(response.share_id);
    await copyText(url);
    message.success('分享链接已生成并复制');
    return { shareUrl: url };
  } catch (error) {
    console.error('创建分享链接失败:', error);
    reportError(error, 'result/createShare');
    message.error('创建分享链接失败，请稍后重试');
    return prevState;
  }
};

const ResultDisplay = ({ result, variant = 'default' }: ResultDisplayProps) => {
  const [shareState, createShareLink, isSharing] = useActionState(
    shareResultAction,
    initialShareState,
  );
  const isMinimal = variant === 'minimal';
  const title = result?.title || '生成结果';
  const content = result?.content || result?.message || '暂无可展示内容';
  const resultHashtags = result?.hashtags;
  const hashtags: string[] = Array.isArray(resultHashtags) ? resultHashtags : [];

  if (!result) {
    return null;
  }

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
          loading={isSharing}
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
          生成分享链接
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
