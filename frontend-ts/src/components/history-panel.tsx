import { useState } from 'react';
import { Card, Button, List, Empty, Popconfirm } from 'antd';
import { HistoryOutlined, RightOutlined } from '@ant-design/icons';
import { formatTimestamp } from '../utils/helper';

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
  const { history, onSelectHistory, onDeleteHistory, currentSessionId } = props;
  const [expanded, setExpanded] = useState(true);

  const handleDelete = (id: string) => {
    onDeleteHistory(id);
  };

  return (
    <Card
      title={
        <div className="flex items-center justify-between cursor-pointer" onClick={() => setExpanded(!expanded)}>
          <span className="font-bold flex items-center gap-2">
            <HistoryOutlined />
            历史记录
          </span>
          <RightOutlined className={`transition-transform ${expanded ? 'rotate-90' : ''}`} />
        </div>
      }
      className="w-[280px] flex-shrink-0"
      bodyStyle={{ padding: 0 }}
    >
      {expanded && (
        <div className="p-4">
          {history.length === 0 ? (
            <Empty description="暂无历史记录" />
          ) : (
            <List
              dataSource={history}
              renderItem={(item) => (
                <List.Item
                  key={item.id}
                  className={`cursor-pointer p-3 rounded-lg mb-2 transition-all ${
                    item.id === currentSessionId
                      ? 'bg-purple-50 border border-purple-200'
                      : 'hover:bg-gray-50'
                  }`}
                  onClick={() => onSelectHistory(item)}

                >
                  <div className="flex flex-col">
                    <span className="text-sm font-medium text-gray-800 truncate">
                      {item.title || item.userInput}
                    </span>
                    <span className="text-xs text-gray-400 mt-1">
                      {formatTimestamp(item.timestamp)}
                    </span>
                  </div>
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
