import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  Layout,
  Input,
  Button,
  Space,
  message,
  Typography,
  Select,
  Card,
} from 'antd';
import {
  SendOutlined,
  HistoryOutlined,
  StopOutlined,
} from '@ant-design/icons';
import {
  createDialogGenerateRequest,
  generateDialogContent,
  type UserInput,
} from '../services/api';
import { List, RowComponentProps, useListRef } from 'react-window';
import AgentLogs from '../components/agent-logs';
import ResultDisplay from '../components/result-display';
import { HistoryItem } from '../components/history-panel';
import { useSSEClient } from '../hooks/use-sse-client';

const { Header, Content } = Layout;
const { Text, Paragraph, Title } = Typography;

interface Message {
  id: string;
  type: 'user' | 'system';
  content: string;
  timestamp: number;
}

interface Version {
  id: number;
  timestamp: number;
  content: string;
  title: string;
  hashtags: string[];
  imageUrl: string;
}

type StreamEvent =
  | {
      type: 'log';
      data: {
        from: string;
        message: string;
      };
    }
  | {
      type: 'result';
      data: any;
    };

type LogType = {
  agent_name: string;
  message: string;
  timestamp: string;
};

interface MessageRowData {
  messages: Message[];
}

const MESSAGE_BASE_HEIGHT = 56;
const MESSAGE_LINE_HEIGHT = 24;
const MESSAGE_CHARS_PER_LINE = 18;
const MESSAGE_MAX_HEIGHT = 640;

const estimateMessageRowHeight = (content: string) => {
  const lineCount = content
    .split('\n')
    .reduce((total, line) => total + Math.max(1, Math.ceil(line.length / MESSAGE_CHARS_PER_LINE)), 0);

  return MESSAGE_BASE_HEIGHT + lineCount * MESSAGE_LINE_HEIGHT;
};

const MessageRow = ({ index, style, messages }: RowComponentProps<MessageRowData>) => {
  const messageItem = messages[index];

  return (
    <div style={{ ...style, boxSizing: 'border-box', paddingBottom: '8px' }}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          boxSizing: 'border-box',
          paddingBottom: '8px',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <Text strong>{messageItem.type === 'user' ? '用户' : '系统'}</Text>
        <Paragraph style={{ marginBottom: '4px' }}>{messageItem.content}</Paragraph>
        <Text type="secondary" style={{ fontSize: '12px' }}>
          {new Date(messageItem.timestamp).toLocaleString()}
        </Text>
      </div>
    </div>
  );
};

const DialogContent: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [versions, setVersions] = useState<Version[]>([]);
  const [currentVersion, setCurrentVersion] = useState<number>(-1);
  const [inputValue, setInputValue] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  
  // 从 sessionStorage 获取或生成会话 ID
  const getOrCreateSessionId = (): string => {
    const STORAGE_KEY = 'xhs_session_id';
    const sessionStorageId = sessionStorage.getItem(STORAGE_KEY);
    const localStorageId = localStorage.getItem(STORAGE_KEY);
    const stableId = sessionStorageId || localStorageId;

    // 优先复用已有 ID，避免前端重渲染/重载导致会话漂移
    if (stableId) {
      if (!sessionStorageId) {
        sessionStorage.setItem(STORAGE_KEY, stableId);
      }
      if (!localStorageId) {
        localStorage.setItem(STORAGE_KEY, stableId);
      }
      return stableId;
    }

    const newId = `session_${Date.now()}`;
    sessionStorage.setItem(STORAGE_KEY, newId);
    localStorage.setItem(STORAGE_KEY, newId);
    return newId;
  };
  
  const [currentSessionId] = useState<string>(getOrCreateSessionId());
  
  const [logs, setLogs] = useState<LogType[]>([]);
  const [result, setResult] = useState<any>(null);
  const [finishTask, setFinishTask] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const { connect, disconnect } = useSSEClient();
  const virtualListRef = useListRef(null);
  const messageViewportRef = useRef<HTMLDivElement>(null);
  const [viewportHeight, setViewportHeight] = useState(MESSAGE_MAX_HEIGHT);
  const messageRowHeights = useMemo(
    () => messages.map((item) => estimateMessageRowHeight(item.content)),
    [messages]
  );
  const initialized = useRef(false);
  const cancelByUserRef = useRef(false);

  useEffect(() => {
    if(initialized.current) return;
    // 添加系统消息
    const systemMessage: Message = {
      id: `msg_${Date.now() + 1}`,
      type: 'system',
      content:
        '哈喽～我是你的内容创作助手 小H，你可以输入内容描述（例如：推荐一款适合学生党的平价防晒霜，清爽不油腻）我将生成一段图文给你发小红书',
      timestamp: Date.now(),
    };
    initialized.current = true;
    setMessages((prev) => [...prev, systemMessage]);
  }, []);

  useEffect(() => {
    if (messages.length === 0) return;
    virtualListRef.current?.scrollToRow({
      align: 'end',
      index: messages.length - 1,
    });
  }, [messages, virtualListRef]);

  useEffect(() => {
    const container = messageViewportRef.current;
    if (!container) return;

    const syncHeight = () => {
      setViewportHeight(container.clientHeight || MESSAGE_MAX_HEIGHT);
    };

    syncHeight();
    const observer = new ResizeObserver(syncHeight);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const runGeneration = async (prompt: string) => {
    if (!prompt.trim()) return;
    const currentInputValue = prompt.trim();
    cancelByUserRef.current = false;

    // 清空之前的日志和结果
    setLogs([]);
    setFinishTask(false);

    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      type: 'user',
      content: currentInputValue,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setLoading(true);

    try {
      let streamResult: any = null;
      const appendLog = (from: string, text: string) => {
        console.log(`${from}: ${text}`);
        setLogs((prev) => [
          ...prev,
          {
            agent_name: from,
            message: text,
            timestamp: new Date().toISOString(),
          },
        ]);
      };

      const fallbackResult = await connect<StreamEvent, any>({
        createRequest: (signal) =>
          createDialogGenerateRequest(
            {
              prompt: currentInputValue,
              session_id: currentSessionId,
            } satisfies UserInput,
            signal
          ),
        parseMessage: (payload) => JSON.parse(payload) as StreamEvent,
        onMessage: (event) => {
          if (event.type === 'log') {
            appendLog(event.data.from, event.data.message);
          } else if (event.type === 'result') {
            streamResult = event.data;
          }
        },
        fallback: async (error) => {
          console.warn('SSE 连接异常，已切换降级策略:', error);
          message.warning('实时通道异常，正在切换降级模式...');
          return generateDialogContent({
            request: {
              prompt: currentInputValue,
              session_id: currentSessionId,
            },
            log_callback: appendLog,
          });
        },
      });
      const resultData = fallbackResult ?? streamResult;

      if (!resultData) {
        if (cancelByUserRef.current) {
          return;
        }
        throw new Error('未获取到生成结果');
      }

      // 更新结果状态
      setResult(resultData);

      const systemMessage: Message = {
        id: `msg_${Date.now() + 1}`,
        type: 'system',
        content: '已生成内容，请查看下方文案区域',
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, systemMessage]);
      setFinishTask(true);
      const newVersion: Version = {
        id: versions.length,
        timestamp: Date.now(),
        content: resultData.content,
        title: resultData.title,
        hashtags: resultData.hashtags,
        imageUrl: resultData.image_url,
      };
      setVersions((prev) => [...prev, newVersion]);
      setCurrentVersion(newVersion.id);

      const historyItem: HistoryItem = {
        id: currentSessionId,
        userInput: currentInputValue,
        timestamp: Date.now(),
        title: resultData.title,
      };
      setHistory((prev) => [historyItem, ...prev]);
    } catch (error) {
      if (!cancelByUserRef.current) {
        message.error('生成内容失败，请重试');
      }
      console.error('Error generating content:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    await runGeneration(inputValue);
  };

  const handleStopGeneration = () => {
    cancelByUserRef.current = true;
    disconnect();
    setLoading(false);
    message.info('已停止当前生成任务');
  };

  const handleVersionSelect = (versionId: number) => {
    const version = versions[versionId];
    setCurrentVersion(versionId);
    setResult({
      title: version.title,
      content: version.content,
      hashtags: version.hashtags,
      image_url: version.imageUrl,
    });

    const systemMessage: Message = {
      id: `msg_${Date.now()}`,
      type: 'system',
      content: `已切换至版本 V${versionId + 1}`,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, systemMessage]);

    message.success(`已切换至版本 V${versionId + 1}`);
  };

  return (
    <Layout className="min-h-full">
      <Header
        style={{
          backgroundColor: '#fff',
          padding: '0 16px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        }}
      >
        <Title level={4} style={{ margin: '16px 0' }}>
          内容创作助手
        </Title>
      </Header>
      <Layout className="min-h-0">
        <Content className="flex w-full min-w-0">
          <div className="flex w-full min-w-0 flex-col gap-4 lg:h-[calc(100vh-160px)] lg:flex-row">
            {/* 历史记录面板 */}
            {/* <HistoryPanel
              history={history}
              onSelectHistory={handleSelectHistory}
              onDeleteHistory={handleDeleteHistory}
              currentSessionId={currentSessionId}
            /> */}
            
            {/* 聊天窗口 */}
            <Card
              title="聊天记录"
              className="flex min-h-[360px] w-full flex-col lg:h-full lg:w-[min(420px,36vw)] lg:flex-shrink-0"
              styles={{
                body: {
                  display: 'flex',
                  flex: 1,
                  minHeight: 0,
                  flexDirection: 'column',
                },
              }}
            >
              <div ref={messageViewportRef} className="flex-1 min-h-0 mb-4">
                <List
                  rowComponent={MessageRow}
                  rowCount={messages.length}
                  rowHeight={(index) => messageRowHeights[index] ?? MESSAGE_BASE_HEIGHT}
                  rowProps={{ messages }}
                  overscanCount={2}
                  style={{ height: viewportHeight, width: '100%' }}
                  listRef={virtualListRef}
                />
              </div>

              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder="请输入您的需求..."
                  onPressEnter={handleSubmit}
                  className="flex-1"
                />
                <Space>
                  {loading ? (
                    <Button
                      danger
                      type="primary"
                      icon={<StopOutlined />}
                      onClick={handleStopGeneration}
                    >
                      停止生成
                    </Button>
                  ) : (
                    <Button
                      type="primary"
                      icon={<SendOutlined />}
                      onClick={handleSubmit}
                      disabled={loading}
                    >
                      发送
                    </Button>
                  )}
                </Space>
              </div>
            </Card>

            {/* 右侧内容区 */}
            <div className="flex min-w-0 flex-1 flex-col overflow-x-hidden lg:h-full lg:overflow-y-auto">
              {/* 版本选择器 */}
              <Card title="文案版本" extra={<HistoryOutlined />}>
                <Select
                  value={currentVersion}
                  onChange={handleVersionSelect}
                  style={{ width: '100%' }}
                  placeholder="选择版本"
                >
                  {versions.map((version) => (
                    <Select.Option key={version.id} value={version.id}>
                      V{version.id + 1} -{" "}
                      {new Date(version.timestamp).toLocaleString()}
                    </Select.Option>
                  ))}
                </Select>
              </Card>

              {/* 生成结果展示 */}
              {result ? (
                <Card title="生成结果" className="mt-4">
                  <ResultDisplay result={result} />
                </Card>
              ) : null}

              {/* Agent 日志 */}
              <AgentLogs
                logs={logs}
                isCollapse={finishTask}
                isLoading={loading}
              />
            </div>
          </div>
        </Content>
      </Layout>
    </Layout>
  );
};

export default DialogContent;
