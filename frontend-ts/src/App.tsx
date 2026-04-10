import React, {useState} from 'react';
import InputForm from './components/input-form';
import AgentLogs from './components/agent-logs';
import ResultDisplay from './components/result-display';
import DialogContent from './pages/dialog-content';
import {LogType} from './types'

import './App.css';
import { generateContent } from './services/api';

import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UserOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons';
import { Button, Layout, Menu, theme } from 'antd';

const { Header, Sider, Content } = Layout;

const App: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken();
  const [logs, setLogs] = useState<LogType[]>([]);
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [activeMenu, setActiveMenu] = useState('1');
  
  const handleSubmit = async (prompt:string) => {
    setLogs([]);
    setResult(null);
    setIsLoading(true);

    try {
      await generateContent(
       { prompt,
        onLog:(log) => {
          setLogs(prevLogs => [...prevLogs, log]);
        },
        onResult:(resultData) => {
          setResult(resultData);
          setIsLoading(false);
        },
        onError:(error) => {
          console.error('生成失败:', error);
          setIsLoading(false);
        }}
      );
    } catch (error) {
      console.error('生成失败:', error);
      setIsLoading(false);
    }
  };

  return (
    <Layout className="w-full h-full">
      <Sider trigger={null} collapsible collapsed={collapsed}>
        <div className="demo-logo-vertical" />
        <Menu
          theme="dark"
          mode="inline"
          defaultSelectedKeys={[activeMenu]}
          onClick={({ key }) => setActiveMenu(key)}
          items={[
            {
              key: '1', 
              icon: <UserOutlined />,
              label: '一次性生成内容',
            },
            {
              key: '2',
              icon: <VideoCameraOutlined />,
              label: '多轮对话生成内容',
            },
          ]}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: 0, background: colorBgContainer }}>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{
              fontSize: '16px',
              width: 64,
              height: 64,
            }}
          />
          <h1>小红书内容生成器</h1>
        </Header>
        <Content
          style={{
            margin: '24px 16px',
            padding: 24,
            minHeight: 280,
            background: colorBgContainer,
            borderRadius: borderRadiusLG,
          }}
        >
         {activeMenu==='1'?( <div className="app">
            <InputForm onSubmit={handleSubmit} isLoading={isLoading} />
            <AgentLogs logs={logs} />
            <ResultDisplay result={result} />
          </div>):(<DialogContent />)}
        </Content>
      </Layout>
    </Layout>
  );
};

export default App;