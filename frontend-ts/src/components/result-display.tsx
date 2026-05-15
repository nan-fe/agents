import React from 'react';
import ReactMarkdown from 'react-markdown';

const ResultDisplay = (params: { result?: any }) => {
  const { result } = params;
  if (!result) {
    return null;
  }

  const title = result.title || '生成结果';
  const content = result.content || result.message || '暂无可展示内容';
  const hashtags = Array.isArray(result.hashtags) ? result.hashtags : [];

  return (
    <div className="flex flex-col gap-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-xl font-bold text-gray-800 mb-4">{title}</h3>
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