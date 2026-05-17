'use client';

import { useEffect, useMemo, useState } from 'react';

type ShareActionsProps = {
  title: string;
  content: string;
  hashtags: string[];
};

const buttonClass =
  'rounded-full border border-pink-300 bg-white px-4 py-2.5 text-pink-700 transition hover:border-pink-500 hover:text-pink-800';

const primaryButtonClass =
  'rounded-full border border-pink-600 bg-pink-600 px-4 py-2.5 text-white transition hover:bg-pink-700';

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
    [content, hashtags, title]
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
    <div className="mt-7 flex flex-wrap gap-3">
      <button
        className={primaryButtonClass}
        type="button"
        onClick={() => handleCopy('链接', currentUrl)}
      >
        复制链接
      </button>
      <button
        className={buttonClass}
        type="button"
        onClick={() => handleCopy('文案', shareText)}
      >
        复制文案
      </button>
      <a className={buttonClass} href={xUrl} target="_blank" rel="noreferrer">
        分享到 X
      </a>
      <a
        className={buttonClass}
        href={weiboUrl}
        target="_blank"
        rel="noreferrer"
      >
        分享到微博
      </a>
    </div>
  );
};

export default ShareActions;
