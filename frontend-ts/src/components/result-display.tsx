import React, { useMemo, useState } from 'react';
import { Button, Space, message } from 'antd';
import ReactMarkdown from 'react-markdown';
import {
  buildShareUrl,
  createShare,
  type ShareResult,
} from '../services/api';

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

const ResultDisplay = (params: { result?: ShareResult }) => {
  const { result } = params;
  const [shareUrl, setShareUrl] = useState('');
  const [sharing, setSharing] = useState(false);
  const title = result?.title || '生成结果';
  const content = result?.content || result?.message || '暂无可展示内容';
  const resultHashtags = result?.hashtags;
  const hashtags: string[] = Array.isArray(resultHashtags) ? resultHashtags : [];
  const shareText = useMemo(
    () => [title, content, hashtags.map((tag) => `#${tag}`).join(' ')].filter(Boolean).join('\n\n'),
    [content, hashtags, title]
  );

  if (!result) {
    return null;
  }

  const handleCreateShare = async () => {
    try {
      setSharing(true);
      const response = await createShare(result);
      const url = buildShareUrl(response.share_id);
      setShareUrl(url);
      await copyText(url);
      message.success('分享链接已生成并复制');
    } catch (error) {
      console.error('创建分享链接失败:', error);
      message.error('创建分享链接失败，请稍后重试');
    } finally {
      setSharing(false);
    }
  };


  return (
    <div className="flex flex-col gap-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex flex-col gap-3 mb-4 sm:flex-row sm:items-start sm:justify-between">
          <h3 className="text-xl font-bold text-gray-800 m-0">{title}</h3>
          <Space wrap>
            <Button type="primary" loading={sharing} onClick={handleCreateShare}>
              生成分享链接
            </Button>
          </Space>
        </div>
        <div className="text-gray-700 leading-relaxed">
          <ReactMarkdown>{content}</ReactMarkdown>
        </div>
        <div className="flex flex-wrap gap-2 mt-4">
          {hashtags.map((tag: string, index: number) => (
            <span
              key={index}
              className="px-3 py-1 bg-pink-100 text-pink-600 rounded-full text-sm"
            >
              {tag}
            </span>
          ))}
        </div>
        {shareUrl && (
          <div className="mt-4 rounded-md bg-pink-50 p-3 text-sm text-gray-700">
            <div className="mb-2 font-medium text-pink-600">分享链接已生成</div>
            <div className="break-all">{shareUrl}</div>
            <Space wrap className="mt-3">
              <Button size="small" onClick={() => copyText(shareUrl)}>
                复制链接
              </Button>
              <Button size="small" type="link" href={shareUrl} target="_blank">
                打开分享页
              </Button>
            </Space>
          </div>
        )}
      </div>
      {result.image_url && (
        <div className="bg-white rounded-lg shadow-md p-4">
          <img
            src={result.image_url}
            alt="生成的图片"
            className="w-full h-auto rounded-lg max-h-96 object-contain"
          />
        </div>
      )}
    </div>
  );
};

export default ResultDisplay;