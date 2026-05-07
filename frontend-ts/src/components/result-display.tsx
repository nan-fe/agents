import React from 'react';
import ReactMarkdown from 'react-markdown';

const ResultDisplay = (params: { result?: any }) => {
  const { result } = params;
  if (!result) {
    return null;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-xl font-bold text-gray-800 mb-4">{result.title}</h3>
        <div className="text-gray-700 leading-relaxed">
          <ReactMarkdown>{result.content}</ReactMarkdown>
        </div>
        <div className="flex flex-wrap gap-2 mt-4">
          {result.hashtags.map((tag: string, index: number) => (
            <span
              key={index}
              className="px-3 py-1 bg-pink-100 text-pink-600 rounded-full text-sm"
            >
              {tag}
            </span>
          ))}
        </div>
      </div>
      <div className="bg-white rounded-lg shadow-md p-4">
        {result.image_url && (
          <img
            src={result.image_url}
            alt="生成的图片"
            className="w-full h-auto rounded-lg max-h-96 object-contain"
          />
        )}
      </div>
    </div>
  );
};

export default ResultDisplay;