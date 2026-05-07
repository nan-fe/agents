import React, { useState } from 'react';
import {
  UserOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons';
import { Layout, Menu, theme } from 'antd';
import DialogContent from './pages/dialog-content';

import './App.css';

const { Sider, Content } = Layout;
enum PageMenu {
  DIALOG_CONTENT = 1,
  PRODUCT_MARKETING,
}
/**
 * TODO: 菜单后续会新增选品池，目前仅支持内容生成
 */
const App: React.FC = () => {
  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken();
  const [activeMenu, setActiveMenu] = useState(String(PageMenu.DIALOG_CONTENT));

  return (
    <Layout className="w-full h-full">
      <Sider trigger={null} collapsible>
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
      <Content
        style={{
          padding: 24,
          minHeight: 280,
          background: colorBgContainer,
          borderRadius: borderRadiusLG,
        }}
      >
        <DialogContent />
      </Content>
    </Layout>
  );
};

export default App;
