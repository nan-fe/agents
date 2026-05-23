import React, { useState } from 'react';
import {
  LogoutOutlined,
  UserOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons';
import { Button, Layout, Menu, theme } from 'antd';
import DialogContent from './pages/dialog-content';

import './App.css';

const { Sider, Content, Header } = Layout;
enum PageMenu {
  DIALOG_CONTENT = 1,
  PRODUCT_MARKETING,
}

const handleLogout = () => {
  window.location.assign('/logout');
};

/**
 * TODO: 菜单后续会新增选品池，目前仅支持内容生成
 */
const App: React.FC = () => {
  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken();
  const [activeMenu, setActiveMenu] = useState(String(PageMenu.DIALOG_CONTENT));

  return (
    <Layout className="min-h-screen w-full">
      <Sider breakpoint="lg" collapsedWidth={0} trigger={null} collapsible>
        <div className="demo-logo-vertical" />
        <Menu
          theme="dark"
          mode="inline"
          defaultSelectedKeys={[activeMenu]}
          onClick={({ key }) => setActiveMenu(key)}
          items={[
            {
              key: String(PageMenu.DIALOG_CONTENT),
              icon: <VideoCameraOutlined />,
              label: '多轮对话生成内容',
            },
            {
              key: String(PageMenu.PRODUCT_MARKETING),
              icon: <UserOutlined />,
              label: '选品池（待建设）',
            },
          ]}
        />
      </Sider>
      <Layout>
        <Header className="flex items-center justify-end border-b border-gray-200 bg-white px-4 !leading-normal">
          <Button icon={<LogoutOutlined />} onClick={handleLogout}>
            退出登录
          </Button>
        </Header>
        <Content
          className="min-w-0"
          style={{
            padding: 16,
            minHeight: 280,
            background: colorBgContainer,
            borderRadius: borderRadiusLG,
          }}
        >
          <DialogContent />
        </Content>
      </Layout>
    </Layout>
  );
};

export default App;
