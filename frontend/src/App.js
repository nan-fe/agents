import React, { useState } from 'react';
import InputForm from './components/InputForm';
import AgentLogs from './components/AgentLogs';
import ResultDisplay from './components/ResultDisplay';
import { generateContent } from './services/api';

function App() {
  const [logs, setLogs] = useState([]);
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (prompt) => {
    setLogs([]);
    setResult(null);
    setIsLoading(true);

    try {
      await generateContent(
        prompt,
        (log) => {
          setLogs(prevLogs => [...prevLogs, log]);
        },
        (resultData) => {
          setResult(resultData);
          setIsLoading(false);
        },
        (error) => {
          console.error('生成失败:', error);
          setIsLoading(false);
        }
      );
    } catch (error) {
      console.error('生成失败:', error);
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <h1>小红书内容生成器</h1>
      <InputForm onSubmit={handleSubmit} isLoading={isLoading} />
      <AgentLogs logs={logs} />
      <ResultDisplay result={result} />
    </div>
  );
}

export default App;
