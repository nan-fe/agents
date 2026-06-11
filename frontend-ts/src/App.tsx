import React, { useState } from 'react';
import {
  LogoutOutlined,
  PlusOutlined,
  UserOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons';
import { Layout, Menu, Modal, message } from 'antd';
import DialogContent from './pages/dialog-content';
import { startNewConversation } from './utils/new-conversation';

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
  const [activeMenu, setActiveMenu] = useState(String(PageMenu.DIALOG_CONTENT));
  const [chatSessionKey, setChatSessionKey] = useState(0);

  const handleNewChat = () => {
    Modal.confirm({
      title: '开始新对话？',
      content: '当前会话将保存到项目档案，并创建新的创作项目。',
      okText: '新对话',
      cancelText: '取消',
      onOk: async () => {
        try {
          await startNewConversation();
          setChatSessionKey((key) => key + 1);
          message.success('已开始新对话');
        } catch (error) {
          console.error('开始新对话失败:', error);
          message.error('开始新对话失败，请稍后重试');
        }
      },
    });
  };

  return (
    <Layout className="atelier-canvas h-screen w-full overflow-hidden font-body">
      <Sider
        breakpoint="lg"
        collapsedWidth={0}
        trigger={null}
        collapsible
        className="atelier-studio-sider flex !h-screen flex-col !fixed lg:!relative"
        width={220}
      >
        <div className="flex flex-col items-center border-b border-gold/30 px-3 py-5">
          <p className="atelier-eyebrow text-gold-light">Atelier</p>
          <h2 className="mt-1 font-display text-xs font-semibold tracking-[0.18em] text-ivory">
            创作画室
          </h2>
        </div>
        <button
          className="chat-sidebar-new mx-3 mt-3 flex w-[calc(100%-1.5rem)] items-center justify-center gap-2 rounded-sm border border-dashed border-gold/45 bg-transparent px-3 py-2 font-display text-[0.65rem] font-semibold uppercase tracking-widest text-[#e8dcc4] transition-colors hover:border-gold hover:text-gold-light focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gold"
          type="button"
          onClick={handleNewChat}
        >
          <PlusOutlined aria-hidden="true" />
          新对话
        </button>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[activeMenu]}
          onClick={({ key }) => setActiveMenu(key)}
          items={[
            {
              key: String(PageMenu.DIALOG_CONTENT),
              icon: <VideoCameraOutlined />,
              label: '内容生成',
            },
            {
              key: String(PageMenu.PRODUCT_MARKETING),
              icon: <UserOutlined />,
              label: '选品池（待建设）',
              disabled: true,
            },
          ]}
        />
        <div className="mt-auto border-t border-gold/20 p-3">
          <a className="studio-logout-link" href="/logout">
            <LogoutOutlined aria-hidden="true" />
            退出画室
          </a>
        </div>
      </Sider>
      <Layout className="min-h-0 min-w-0 flex-1 bg-transparent">
        <Content className="flex h-screen min-h-0 min-w-0 flex-col overflow-hidden p-0">
          <DialogContent key={chatSessionKey} />
        </Content>
      </Layout>
    </Layout>
  );
};

export default App;
