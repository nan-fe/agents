'use client';

import { useEffect, useMemo, useState } from 'react';

type ShareActionsProps = {
  title: string;
  content: string;
  hashtags: string[];
};

const copyText = async (text: string) => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textArea = document.createElement('textarea');
  textArea.value = text;
  textArea.className = 'fixed -left-[9999px]';
  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();
  document.execCommand('copy');
  document.body.removeChild(textArea);
};

const ShareActions = ({
  title,
  content,
  hashtags,
}: ShareActionsProps) => {
  const [copied, setCopied] = useState('');
  const [currentUrl, setCurrentUrl] = useState('');
  const shareText = useMemo(
    () =>
      [title, content, hashtags.map((tag) => `#${tag}`).join(' ')]
        .filter(Boolean)
        .join('\n\n'),
    [content, hashtags, title],
  );

  useEffect(() => {
    setCurrentUrl(window.location.href);
  }, []);

  const encodedUrl = encodeURIComponent(currentUrl);
  const encodedText = encodeURIComponent(`${title}\n${content.slice(0, 120)}`);
  const xUrl = `https://twitter.com/intent/tweet?text=${encodedText}&url=${encodedUrl}`;
  const weiboUrl = `https://service.weibo.com/share/share.php?url=${encodedUrl}&title=${encodedText}`;

  const handleCopy = async (label: string, text: string) => {
    await copyText(text);
    setCopied(label);
    window.setTimeout(() => setCopied(''), 1600);
  };

  return (
    <div className="mt-8 flex flex-wrap gap-3">
      <p aria-live="polite" className="sr-only">
        {copied ? `已复制${copied}` : ''}
      </p>
      <button
        className="atelier-btn-primary"
        type="button"
        onClick={() => handleCopy('链接', currentUrl)}
      >
        {copied === '链接' ? '已复制' : '复制链接'}
      </button>
      <button
        className="atelier-btn-ghost"
        type="button"
        onClick={() => handleCopy('文案', shareText)}
      >
        {copied === '文案' ? '已复制' : '复制文案'}
      </button>
      <a
        className="atelier-btn-ghost"
        href={xUrl}
        target="_blank"
        rel="noopener noreferrer"
      >
        分享到 X
      </a>
      <a
        className="atelier-btn-ghost"
        href={weiboUrl}
        target="_blank"
        rel="noopener noreferrer"
      >
        分享到微博
      </a>
    </div>
  );
};

export default ShareActions;
