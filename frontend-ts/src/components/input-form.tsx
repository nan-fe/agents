
import React, {useState} from 'react';
const InputForm = (param:{ onSubmit:(val:string)=>void, isLoading:boolean }) => {
    
    const [prompt, setPrompt] = useState('');
    const {isLoading,onSubmit} = param;

  const handleSubmit = (e:React.SubmitEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (prompt.trim() && !isLoading) {
      onSubmit(prompt.trim());
    //   setPrompt('');
    }
  };

  return (
    <form className="input-form" onSubmit={handleSubmit}>
      <label htmlFor="prompt">请输入内容描述（例如：推荐一款适合学生党的平价防晒霜，清爽不油腻）：</label>
      <textarea
        id="prompt"
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="输入您的需求..."
        disabled={isLoading}
      />
      <button type="submit" disabled={isLoading || !prompt.trim()}>
        {isLoading ? '生成中...' : '生成内容'}
      </button>
    </form>
  );
};

export default InputForm;
