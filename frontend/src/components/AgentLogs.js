import React from 'react';
import { formatTimestamp } from '../utils/helpers';

const AgentLogs = ({ logs }) => {
  return (
    <div className="agent-logs">
      <h2>Agent 思考过程</h2>
      {logs.length === 0 ? (
        <p>等待生成中...</p>
      ) : (
        logs.map((log, index) => (
          <div key={index} className="log-item">
            <div className="agent-name">
              {log.agent_name} <span className="timestamp">{formatTimestamp(log.timestamp)}</span>
            </div>
            <div className="log-message">{log.message}</div>
          </div>
        ))
      )}
    </div>
  );
};

export default AgentLogs;
