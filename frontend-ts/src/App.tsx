import React, {useState} from 'react';
import InputForm from './components/input-form';
import AgentLogs from './components/agent-logs';
import ResultDisplay from './components/result-display';
import {LogType} from './types'

import './App.css';
import { generateContent } from './services/api';

function App() {
  const [logs, setLogs] = useState<LogType[]>([]);
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (prompt:string) => {
    setLogs([]);
    setResult(null);
    setIsLoading(true);

    try {
      await generateContent(
       { prompt,
        onLog:(log) => {
          setLogs(prevLogs => [...prevLogs, log]);
        },
        onResult:(resultData) => {
          setResult(resultData);
          setIsLoading(false);
        },
        onError:(error) => {
          console.error('生成失败:', error);
          setIsLoading(false);
        }}
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
