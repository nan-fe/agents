"use client";
import { useState } from 'react';
import { Card, List, Empty } from 'antd';
import { HistoryOutlined, RightOutlined } from '@ant-design/icons';
import { formatTimestamp } from '../../../lib/timestamp';

export interface HistoryItem {
  id: string;
  userInput: string;
  timestamp: number;
  title?: string;
}

interface HistoryPanelProps {
  history: HistoryItem[];
  onSelectHistory: (item: HistoryItem) => void;
  onDeleteHistory: (id: string) => void;
  currentSessionId: string;
}

const HistoryPanel = (props: HistoryPanelProps) => {
  const { history, onSelectHistory, currentSessionId } = props;
  const [expanded, setExpanded] = useState(true);

  return (
    <Card
      title={
        <button
          type="button"
          className="flex w-full cursor-pointer items-center justify-between border-0 bg-transparent p-0 text-left"
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
        >
          <span className="flex items-center gap-2 font-bold">
            <HistoryOutlined aria-hidden="true" />
            历史记录
          </span>
          <RightOutlined
            aria-hidden="true"
            className={`transition-transform ${expanded ? 'rotate-90' : ''}`}
          />
        </button>
      }
      className="atelier-panel-frame w-[280px] flex-shrink-0"
      styles={{ body: { padding: 0 } }}
    >
      {expanded && (
        <div className="p-4">
          {history.length === 0 ? (
            <Empty description="暂无历史记录" />
          ) : (
            <List
              dataSource={history}
              renderItem={(item) => (
                <List.Item className="!border-0 !p-0">
                  <button
                    type="button"
                    className={`mb-2 w-full cursor-pointer rounded-sm p-3 text-left transition-colors ${
                      item.id === currentSessionId
                        ? 'border border-gold bg-gold/10'
                        : 'hover:bg-canvas/80'
                    }`}
                    onClick={() => onSelectHistory(item)}
                  >
                    <div className="flex flex-col">
                      <span className="truncate font-body text-sm font-medium text-ink">
                        {item.title || item.userInput}
                      </span>
                      <span className="mt-1 font-body text-xs italic text-ink-muted">
                        {formatTimestamp(item.timestamp)}
                      </span>
                    </div>
                  </button>
                </List.Item>
              )}
            />
          )}
        </div>
      )}
    </Card>
  );
};

export default HistoryPanel;
