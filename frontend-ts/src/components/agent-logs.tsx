import React, { useState } from 'react';
import { Card, Collapse } from 'antd';
import { LogType } from '../types';
import { formatTimestamp } from '../utils/helper';

interface IAgentLog {
  logs: LogType[];
  title?: string;
  isCollapse?: boolean;
}
const AgentLogs = (param: IAgentLog) => {
  const { logs, title, isCollapse = false } = param;
  const [isColl, setIsColl] = useState(isCollapse);

  return (
    <Collapse
      collapsible="icon"
      className="mt-4 bg-white"
      onChange={(key) => {
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
                <p className="text-gray-500">等待生成中...</p>
              ) : (
                logs.map((log: any, index: number) => (
                  <div key={index} className="border-b border-gray-100 pb-3 mb-3 last:border-b-0 last:pb-0 last:mb-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-purple-600">{log.agent_name}</span>
                      <span className="text-xs text-gray-400">{formatTimestamp(log.timestamp)}</span>
                    </div>
                    <div className="text-gray-700 break-words text-sm">{log.message}</div>
                  </div>
                ))
              )}
            </Card>
          ),
        },
      ]}
    ></Collapse>
  );
};

export default AgentLogs;