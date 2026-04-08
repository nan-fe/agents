import React from 'react';
import ReactMarkdown from 'react-markdown';

const ResultDisplay = (params:{ result?:any }) => {
    const {result} =params;
  if (!result) {
    return null;
  }

  return (
    <div className="result-display">
      <h2>生成结果</h2>
      <div className="result-content">
        <h3>{result.title}</h3>
        <div className="content">
          <ReactMarkdown>{result.content}</ReactMarkdown>
        </div>
        <div className="hashtags">
          {result.hashtags.map((tag:string, index:number) => (
            <span key={index} className="hashtag">{tag}</span>
          ))}
        </div>
      </div>
      <div className="result-image">
        <img src={result.image_url} alt="生成的图片" />
      </div>
    </div>
  );
};

export default ResultDisplay;
