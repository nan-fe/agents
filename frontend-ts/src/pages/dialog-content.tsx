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
  const [sessionId] = useState<string>(`session_${Date.now()}`);
  const [logs, setLogs] = useState<LogType[]>([]);
  const [result, setResult] = useState<any>(null);
  const [finishTask, setFinishTask] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // 添加系统消息
    const systemMessage: Message = {
      id: `msg_${Date.now() + 1}`,
      type: 'system',
      content:
        '哈喽～我是你的内容创作助手 小H，你可以输入内容描述（例如：推荐一款适合学生党的平价防晒霜，清爽不油腻）我将生成一段图文给你发小红书',
      timestamp: Date.now(),
    };
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
    setResult(null);

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
      // 调用API生成内容
      const resultData = await generateDialogContent({
        user_input: inputValue,
        session_id: sessionId,
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

    } catch (error) {
      message.error('生成内容失败，请重试');
      console.error('Error generating content:', error);
    } finally {
      setLoading(false);
    }
  };

  // const handleRollback = async (versionId: number) => {
  //   setLoading(true);
  //   try {
  //     // 模拟回退操作
  //     const version = versions[versionId];
  //     setCurrentVersion(versionId);

  //     // 添加系统消息
  //     const systemMessage: Message = {
  //       id: `msg_${Date.now()}`,
  //       type: 'system',
  //       content: `已回退至V${versionId + 1}`,
  //       timestamp: Date.now(),
  //     };
  //     setMessages((prev) => [...prev, systemMessage]);

  //     message.success(`已回退至V${versionId + 1}`);
  //   } catch (error) {
  //     message.error('回退失败，请重试');
  //     console.error('Error rolling back:', error);
  //   } finally {
  //     setLoading(false);
  //   }
  // };

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
                        style={{ display: 'flex', flexDirection: 'column', marginBottom: '8px' }}
                      >
                        <Text strong>{message.type === 'user' ? '用户' : '系统'}</Text>
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
                  // onChange={handleRollback}
                  style={{ width: '100%' }}
                  placeholder="选择版本"
                  disabled
                >
                  {versions.map((version) => (
                    <Select.Option key={version.id} value={version.id}>
                      V{version.id + 1} - {new Date(version.timestamp).toLocaleString()}
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
              <AgentLogs logs={logs} isCollapse={finishTask} />
            </div>
          </div>
        </Content>
      </Layout>
    </Layout>
  );
};

export default DialogContent;
