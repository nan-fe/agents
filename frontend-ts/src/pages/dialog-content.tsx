import React, { useState, useRef, useEffect } from 'react';
import {
  Layout,
  Input,
  Button,
  message,
  List,
  Typography,
  Select,
  Card,
} from 'antd';
import { SendOutlined, HistoryOutlined } from '@ant-design/icons';
import { generateDialogContent } from '../services/api';
import AgentLogs from '../components/agent-logs';
import ResultDisplay from '../components/result-display';
import HistoryPanel, { HistoryItem } from '../components/history-panel';
import { LogType } from '../types';

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

const DialogContent: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [versions, setVersions] = useState<Version[]>([]);
  const [currentVersion, setCurrentVersion] = useState<number>(-1);
  const [inputValue, setInputValue] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  // const [currentSessionId] = useState<string>(`session_${Date.now()}`);
  const [logs, setLogs] = useState<LogType[]>([]);
  const [result, setResult] = useState<any>(null);
  const [finishTask, setFinishTask] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);

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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async () => {
    if (!inputValue.trim()) return;

    // 清空之前的日志和结果
    setLogs([]);

    // 添加用户消息
    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      type: 'user',
      content: inputValue,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setLoading(true);

    try {
      const newSessionId = `session_${Date.now()}`;
      
      // 调用API生成内容
      const resultData = await generateDialogContent({
        user_input: inputValue,
        session_id: newSessionId,
        log_callback: (from: string, message: string) => {
          console.log(`${from}: ${message}`);
          // 更新日志
          setLogs((prev) => [
            ...prev,
            {
              agent_name: from,
              message: message,
              timestamp: new Date().toISOString(),
            },
          ]);
        },
      });

      // 更新结果状态
      setResult(resultData);

      // 添加系统消息
      const systemMessage: Message = {
        id: `msg_${Date.now() + 1}`,
        type: 'system',
        content: '已生成内容，请查看下方文案区域',
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, systemMessage]);
      setFinishTask(true);
      // 更新版本列表
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

      // 添加到历史记录
      const historyItem: HistoryItem = {
        id: newSessionId,
        userInput: inputValue,
        timestamp: Date.now(),
        title: resultData.title,
      };
      setHistory((prev) => [historyItem, ...prev]);
    } catch (error) {
      message.error('生成内容失败，请重试');
      console.error('Error generating content:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectHistory = (item: HistoryItem) => {
    message.info(`已选择历史记录: ${item.title || item.userInput}`);
  };

  const handleDeleteHistory = (id: string) => {
    setHistory((prev) => prev.filter((item) => item.id !== id));
    message.success('历史记录已删除');
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
    <Layout style={{ height: 'auto' }}>
      <Header
        style={{
          backgroundColor: '#fff',
          padding: '0 24px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        }}
      >
        <Title level={4} style={{ margin: '16px 0' }}>
          内容创作助手
        </Title>
      </Header>
      <Layout>
        <Content className="w-full flex">
          <div className="flex w-full" style={{ height: 'calc(100vh - 160px)' }}>
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
              className="w-[400px] flex flex-col flex-shrink-0"
              style={{ overflowY: 'scroll' }}
            >
              <div className="flex-1 overscroll-y-auto mb-16 h-full pb-8">
                <List
                  dataSource={messages}
                  renderItem={(message) => (
                    <List.Item>
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          marginBottom: "8px",
                        }}
                      >
                        <Text strong>
                          {message.type === "user" ? "用户" : "系统"}
                        </Text>
                        <Paragraph>{message.content}</Paragraph>
                        <Text type="secondary" style={{ fontSize: '12px' }}>
                          {new Date(message.timestamp).toLocaleString()}
                        </Text>
                      </div>
                    </List.Item>
                  )}
                />
                <div ref={messagesEndRef} />
              </div>

              <div className="flex">
                <Input
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder="请输入您的需求..."
                  onPressEnter={handleSubmit}
                  className="flex-1 mr-8"
                />
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={handleSubmit}
                  disabled={loading}
                >
                  发送
                </Button>
              </div>
            </Card>

            {/* 右侧内容区 */}
            <div className="flex-1 flex-col overflow-x-hidden">
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
