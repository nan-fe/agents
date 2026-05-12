import { useState, useEffect } from 'react';
import { Card, Collapse } from 'antd';
import { LogType } from '../types';
import { formatTimestamp } from '../utils/helper';

interface IAgentLog {
  logs: LogType[];
  title?: string;
  isCollapse?: boolean;
  isLoading?: boolean;
  lastLogTime?: number;
}

const AgentLogs = (param: IAgentLog) => {
  const { logs, title, isCollapse = false, isLoading = false } = param;
  const [isColl, setIsColl] = useState(isCollapse);
  const [showThinking, setShowThinking] = useState(false);

  useEffect(() => {
    setIsColl(isCollapse);
  }, [isCollapse]);

  useEffect(() => {
    if (isLoading) {
      // 任务进行中自动展开，保证流式日志可见
      setIsColl(false);
    }
  }, [isLoading]);

  useEffect(() => {
    if (isLoading && logs.length > 0) {
      const timer = setTimeout(() => {
        setShowThinking(true);
      }, 1000);
      return () => clearTimeout(timer);
    } else {
      setShowThinking(false);
    }
  }, [logs, isLoading]);

  return (
    <Collapse
      collapsible="icon"
      className="mt-4 bg-white"
      onChange={() => {
        setIsColl(!isColl);
      }}
      activeKey={isColl ? '' : 'agent_thinking'}
      items={[
        {
          key: 'agent_thinking',
          label: <div className="font-bold">{title || 'Agent 思考过程'}</div>,
          children: (
            <Card key="agent_tinking">
              {logs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8">
                  <p className="text-gray-500 text-sm">暂无内容</p>
                </div>
              ) : (
                <>
                  {logs.map((log: any, index: number) => (
                    <div key={index} className="border-b border-gray-100 pb-3 mb-3 last:border-b-0 last:pb-0 last:mb-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold text-purple-600">{log.agent_name}</span>
                        <span className="text-xs text-gray-400">{formatTimestamp(log.timestamp)}</span>
                      </div>
                      <div className="text-gray-700 break-words text-sm">{log.message}</div>
                    </div>
                  ))}
                  {showThinking && isLoading && (
                    <div className="flex flex-col items-center justify-center py-4 mt-4 border-t border-gray-100">
                      <div className="thinking-dots mb-2">
                        <span className="thinking-dot"></span>
                        <span className="thinking-dot"></span>
                        <span className="thinking-dot"></span>
                      </div>
                      <p className="text-gray-500 text-xs">Agent 思考中...</p>
                    </div>
                  )}
                </>
              )}
            </Card>
          ),
        },
      ]}
    ></Collapse>
  );
};

export default AgentLogs;
