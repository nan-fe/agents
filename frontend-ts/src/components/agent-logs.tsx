import { useState } from 'react';
import { Card, Collapse } from 'antd';
import { formatTimestamp } from '../utils/helper';

type LogType = {
  agent_name: string;
  message: string;
  timestamp: string;
};

interface IAgentLog {
  logs: LogType[];
  title?: string;
  isCollapse?: boolean;
  isLoading?: boolean;
}

const AgentLogs = (param: IAgentLog) => {
  const { logs, title, isCollapse = false, isLoading = false } = param;
  const [collapsed, setCollapsed] = useState(isCollapse);

  const isPanelCollapsed = isLoading ? false : collapsed;
  const activeKey = isPanelCollapsed ? '' : 'agent_thinking';
  const showThinking = isLoading && logs.length > 0;

  return (
    <Collapse
      collapsible="icon"
      className="mt-4 bg-white"
      onChange={() => {
        setCollapsed((prev) => !prev);
      }}
      activeKey={activeKey}
      items={[
        {
          key: 'agent_thinking',
          label: <div className="font-bold">{title || 'Agent 思考过程'}</div>,
          children: (
            <Card key="agent_tinking">
              {logs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8">
                  <p className="text-sm text-gray-500">暂无内容</p>
                </div>
              ) : (
                <>
                  {logs.map((log, index) => (
                    <div
                      key={index}
                      className="mb-3 border-b border-gray-100 pb-3 last:mb-0 last:border-b-0 last:pb-0"
                    >
                      <div className="mb-1 flex items-center justify-between">
                        <span className="font-semibold text-purple-600">{log.agent_name}</span>
                        <span className="text-xs text-gray-400">
                          {formatTimestamp(log.timestamp)}
                        </span>
                      </div>
                      <div className="break-words text-sm text-gray-700">{log.message}</div>
                    </div>
                  ))}
                  {showThinking && (
                    <div className="thinking-indicator mt-4 flex flex-col items-center justify-center border-t border-gray-100 py-4">
                      <div className="thinking-dots mb-2">
                        <span className="thinking-dot" />
                        <span className="thinking-dot" />
                        <span className="thinking-dot" />
                      </div>
                      <p className="text-xs text-gray-500">Agent 思考中...</p>
                    </div>
                  )}
                </>
              )}
            </Card>
          ),
        },
      ]}
    />
  );
};

export default AgentLogs;
