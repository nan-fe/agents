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
  Alert,
  Space,
  Form,
} from 'antd';
import { SendOutlined, EditOutlined, CheckOutlined, HistoryOutlined } from '@ant-design/icons';
import { generateDialogContent } from '../services/api';
import AgentLogs from '../components/agent-logs';
import ResultDisplay from '../components/result-display';
import { LogType } from '../types';

const { Header, Content, Sider } = Layout;
const { Text, Paragraph, Title } = Typography;
const {TextArea} = Input;

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

interface QualityReport {
  approved: boolean;
  feedback: string[];
}

const DialogContent: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [versions, setVersions] = useState<Version[]>([]);
  const [currentVersion, setCurrentVersion] = useState<number>(-1);
  const [currentContent, setCurrentContent] = useState<string>('');
  const [currentTitle, setCurrentTitle] = useState<string>('');
  const [currentHashtags, setCurrentHashtags] = useState<string[]>([]);
  const [qualityReport, setQualityReport] = useState<QualityReport | null>(null);
  const [inputValue, setInputValue] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [editing, setEditing] = useState<boolean>(false);
  const [sessionId] = useState<string>(`session_${Date.now()}`);
  const [logs, setLogs] = useState<LogType[]>([]);
  const [result, setResult] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

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
      timestamp: Date.now()
    };
    setMessages(prev => [...prev, userMessage]);
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
          setLogs(prev => [...prev, {
            agent_name: from,
            message: message,
            timestamp: new Date().toISOString()
          }]);
          // setLogs(prevLogs => [...prevLogs, log]);
        }
      });

      // 更新结果状态
      setResult(resultData);

      // 添加系统消息
      const systemMessage: Message = {
        id: `msg_${Date.now() + 1}`,
        type: 'system',
        content: '已生成内容，请查看下方文案区域',
        timestamp: Date.now()
      };
      setMessages(prev => [...prev, systemMessage]);

      // 更新版本列表
      const newVersion: Version = {
        id: versions.length,
        timestamp: Date.now(),
        content: resultData.content,
        title: resultData.title,
        hashtags: resultData.hashtags,
        imageUrl: resultData.image_url
      };
      setVersions(prev => [...prev, newVersion]);
      setCurrentVersion(newVersion.id);
      setCurrentContent(newVersion.content);
      setCurrentTitle(newVersion.title);
      setCurrentHashtags(newVersion.hashtags);

      // 模拟质检报告
      setQualityReport({
        approved: true,
        feedback: ['可以增加更多用户评价', '建议添加具体使用场景', '优化标题吸引力']
      });
    } catch (error) {
      message.error('生成内容失败，请重试');
      console.error('Error generating content:', error);
    } finally {
      setLoading(false);
    }
  };



  const handleRollback = async (versionId: number) => {
    setLoading(true);
    try {
      // 模拟回退操作
      const version = versions[versionId];
      setCurrentVersion(versionId);
      setCurrentContent(version.content);
      setCurrentTitle(version.title);
      setCurrentHashtags(version.hashtags);

      // 添加系统消息
      const systemMessage: Message = {
        id: `msg_${Date.now()}`,
        type: 'system',
        content: `已回退至V${versionId + 1}`,
        timestamp: Date.now()
      };
      setMessages(prev => [...prev, systemMessage]);

      message.success(`已回退至V${versionId + 1}`);
    } catch (error) {
      message.error('回退失败，请重试');
      console.error('Error rolling back:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleEditSubmit = () => {
    if (!currentContent.trim()) return;

    const editMessage: Message = {
      id: `msg_${Date.now()}`,
      type: 'user',
      content: `请基于以下修改更新全文：${currentContent}`,
      timestamp: Date.now()
    };
    setMessages(prev => [...prev, editMessage]);
    setEditing(false);
    handleSubmit();
  };

  return (
    <Layout style={{ height: 'auto' }}>
      <Header style={{ backgroundColor: '#fff', padding: '0 24px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
        <Title level={4} style={{ margin: '16px 0' }}>内容创作助手</Title>
      </Header>
      
      <Layout>
        <Content style={{ padding: '24px', overflow: 'auto' }}>
          <div style={{ display: 'flex', gap: '24px', height: 'calc(100vh - 160px)' }}>
            {/* 聊天窗口 */}
            <Card title="聊天记录" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <div style={{ flex: 1, overflow: 'auto', marginBottom: '16px' }}>
                <List
                  dataSource={messages}
                  renderItem={(message) => (
                    <List.Item>
                      <div style={{ display: 'flex', flexDirection: 'column', marginBottom: '12px' }}>
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
              
              <div style={{ display: 'flex' }}>
                <Input
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder="请输入您的需求..."
                  onPressEnter={handleSubmit}
                  style={{ flex: 1, marginRight: '8px' }}
                />
                <Button type="primary" icon={<SendOutlined />} onClick={handleSubmit} disabled={loading}>
                  发送
                </Button>
              </div>
            </Card>

            {/* 右侧内容区 */}
            <div style={{ flex: 2, display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* 版本选择器 */}
              <Card title="文案版本" extra={<HistoryOutlined />}>
                <Select
                  value={currentVersion}
                  onChange={handleRollback}
                  style={{ width: '100%' }}
                  placeholder="选择版本"
                >
                  {versions.map((version) => (
                    <Select.Option key={version.id} value={version.id}>
                      V{version.id + 1} - {new Date(version.timestamp).toLocaleString()}
                    </Select.Option>
                  ))}
                </Select>
              </Card>

              {/* 生成结果展示 */}
              <Card title="生成结果">
                <ResultDisplay result={result} />
              </Card>

                {/* Agent 日志 */}
              <Card title="Agent 思考过程">
                <AgentLogs logs={logs} />
              </Card>

              {/* 文案内容 */}
              <Card title="当前文案" extra={
                <Space>
                  {editing ? (
                    <Button icon={<CheckOutlined />} onClick={handleEditSubmit}>保存</Button>
                  ) : (
                    <Button icon={<EditOutlined />} onClick={() => setEditing(true)}>编辑</Button>
                  )}
                </Space>
              }>
                <Form layout="vertical">
                  <Form.Item label="标题">
                    <Input
                      value={currentTitle}
                      onChange={(e) => setCurrentTitle(e.target.value)}
                      disabled={!editing}
                    />
                  </Form.Item>
                  <Form.Item label="内容">
                    <TextArea
                      value={currentContent}
                      onChange={(e) => setCurrentContent(e.target.value)}
                      rows={8}
                      disabled={!editing}
                    />
                  </Form.Item>
                  <Form.Item label="标签">
                    <Input
                      value={currentHashtags.join(', ')}
                      onChange={(e) => setCurrentHashtags(e.target.value.split(',').map(tag => tag.trim()))}
                      disabled={!editing}
                      placeholder="用逗号分隔多个标签"
                    />
                  </Form.Item>
                </Form>
              </Card>

              {/* 质检报告 */}
              <Card title="质检报告">
                {qualityReport ? (
                  <div>
                    <Alert
                      message={qualityReport.approved ? '审核通过' : '审核未通过'}
                      type={qualityReport.approved ? 'success' : 'error'}
                      showIcon
                      style={{ marginBottom: '16px' }}
                    />
                    <Title level={5}>改进建议：</Title>
                    <List
                      dataSource={qualityReport.feedback}
                      renderItem={(item) => (
                        <List.Item>
                          <Text>{item}</Text>
                        </List.Item>
                      )}
                    />
                  </div>
                ) : (
                  <Text type="secondary">暂无质检报告</Text>
                )}
              </Card>
            </div>
          </div>
        </Content>
      </Layout>

      {/* {loading && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(255, 255, 255, 0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
          <Spin size="large" tip="生成中..." />
        </div>
      )} */}
    </Layout>
  );
};

export default DialogContent;