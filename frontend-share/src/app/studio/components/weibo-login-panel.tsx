"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import { App, Button, Input, Modal, Space } from 'antd';
import {
  clickWeiboLogin,
  closeWeiboLoginSession,
  getWeiboLoginScreenshotUrl,
  pressWeiboLoginKey,
  reportError,
  startWeiboLoginSession,
  typeWeiboLogin,
  type WeiboLoginStartResponse,
  pollWeiboLoginStatus,
} from '@/services/api';

type WeiboLoginPanelProps = {
  open: boolean;
  onClose: () => void;
  onLoggedIn: () => void;
};

const WeiboLoginPanel = ({ open, onClose, onLoggedIn }: WeiboLoginPanelProps) => {
  const { message } = App.useApp();
  const [session, setSession] = useState<WeiboLoginStartResponse | null>(null);
  const [screenshotTick, setScreenshotTick] = useState(0);
  const [loading, setLoading] = useState(false);
  const [typing, setTyping] = useState('');
  const [currentUrl, setCurrentUrl] = useState('');
  const imgRef = useRef<HTMLImageElement>(null);

  const refreshScreenshot = useCallback(() => {
    setScreenshotTick((value) => value + 1);
  }, []);

  const finishLogin = useCallback(async () => {
    if (session?.session_id) {
      await closeWeiboLoginSession(session.session_id).catch(() => undefined);
    }
    setSession(null);
    onLoggedIn();
    onClose();
    message.success('微博登录成功');
  }, [message, onClose, onLoggedIn, session?.session_id]);

  const handleClose = useCallback(async () => {
    if (session?.session_id) {
      await closeWeiboLoginSession(session.session_id).catch(() => undefined);
    }
    setSession(null);
    onClose();
  }, [onClose, session?.session_id]);

  const startSession = useCallback(async () => {
    setLoading(true);
    try {
      const data = await startWeiboLoginSession();
      if (data.logged_in) {
        await finishLogin();
        return;
      }
      setSession(data);
      setCurrentUrl(data.current_url);
      refreshScreenshot();
    } catch (error) {
      reportError(error, 'social/startWeiboLogin');
      message.error(error instanceof Error ? error.message : '无法启动微博登录');
    } finally {
      setLoading(false);
    }
  }, [finishLogin, message, refreshScreenshot]);

  useEffect(() => {
    if (!open) {
      return;
    }
    void startSession();
    // 仅在弹窗打开时启动一次会话
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open || !session?.session_id) {
      return undefined;
    }

    const interval = window.setInterval(async () => {
      try {
        const status = await pollWeiboLoginStatus(session.session_id);
        setCurrentUrl(status.current_url);
        if (status.logged_in) {
          window.clearInterval(interval);
          await finishLogin();
          return;
        }
        refreshScreenshot();
      } catch {
        // 会话过期时静默停止轮询
      }
    }, 2500);

    return () => window.clearInterval(interval);
  }, [finishLogin, open, refreshScreenshot, session?.session_id]);

  const handleImageClick = async (event: React.MouseEvent<HTMLImageElement>) => {
    if (!session?.session_id || !imgRef.current) {
      return;
    }
    const img = imgRef.current;
    const rect = img.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0 || img.naturalWidth <= 0) {
      return;
    }
    const scaleX = img.naturalWidth / rect.width;
    const scaleY = img.naturalHeight / rect.height;
    const x = (event.clientX - rect.left) * scaleX;
    const y = (event.clientY - rect.top) * scaleY;

    setLoading(true);
    try {
      const result = await clickWeiboLogin(session.session_id, x, y);
      setCurrentUrl(String(result.current_url || ''));
      if (result.logged_in) {
        await finishLogin();
        return;
      }
      refreshScreenshot();
    } catch (error) {
      reportError(error, 'social/clickWeiboLogin');
      message.error(error instanceof Error ? error.message : '点击失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSendText = async () => {
    if (!session?.session_id || !typing.trim()) {
      return;
    }
    setLoading(true);
    try {
      await typeWeiboLogin(session.session_id, typing);
      setTyping('');
      refreshScreenshot();
    } catch (error) {
      reportError(error, 'social/typeWeiboLogin');
      message.error(error instanceof Error ? error.message : '输入失败');
    } finally {
      setLoading(false);
    }
  };

  const handlePressKey = async (key: string) => {
    if (!session?.session_id) {
      return;
    }
    setLoading(true);
    try {
      const result = await pressWeiboLoginKey(session.session_id, key);
      setCurrentUrl(String(result.current_url || ''));
      if (result.logged_in) {
        await finishLogin();
        return;
      }
      refreshScreenshot();
    } catch (error) {
      reportError(error, 'social/pressWeiboLoginKey');
      message.error(error instanceof Error ? error.message : '按键失败');
    } finally {
      setLoading(false);
    }
  };

  const screenshotUrl =
    session?.session_id != null
      ? getWeiboLoginScreenshotUrl(session.session_id, screenshotTick)
      : null;

  return (
    <Modal
      title="微博登录"
      open={open}
      onCancel={() => {
        void handleClose();
      }}
      footer={null}
      width={920}
      destroyOnHidden
    >
      <div className="space-y-3 font-body text-xs text-ink-muted">
        <p>
          在下方页面中点击输入框、切换扫码登录，或用手机微博 App 扫码。
          登录态会保存到服务器 Profile，完成后可自动发微博。
        </p>
        {currentUrl && (
          <p className="truncate text-ink-muted/70">当前页面：{currentUrl}</p>
        )}
        {screenshotUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            ref={imgRef}
            src={screenshotUrl}
            alt="微博登录页"
            className="block h-auto w-full cursor-crosshair select-none rounded-sm border border-gold/20 bg-canvas/60"
            draggable={false}
            onClick={(event) => {
              void handleImageClick(event);
            }}
          />
        ) : (
          <div className="flex h-48 items-center justify-center rounded-sm border border-gold/20 bg-canvas/40">
            {loading ? '正在打开微博…' : '等待会话…'}
          </div>
        )}
        <Space.Compact className="w-full">
          <Input
            value={typing}
            onChange={(event) => setTyping(event.target.value)}
            placeholder="账号 / 验证码（先点击输入框再输入）"
            onPressEnter={() => {
              void handleSendText();
            }}
            disabled={!session?.session_id || loading}
          />
          <Button
            onClick={() => {
              void handleSendText();
            }}
            disabled={!session?.session_id || loading}
          >
            发送
          </Button>
        </Space.Compact>
        <Space wrap>
          <Button
            size="small"
            onClick={() => {
              void handlePressKey('Enter');
            }}
            disabled={!session?.session_id || loading}
          >
            Enter
          </Button>
          <Button
            size="small"
            onClick={() => {
              void handlePressKey('Backspace');
            }}
            disabled={!session?.session_id || loading}
          >
            退格
          </Button>
          <Button
            size="small"
            onClick={() => {
              refreshScreenshot();
            }}
            disabled={!session?.session_id || loading}
          >
            刷新画面
          </Button>
          <Button
            size="small"
            onClick={() => {
              void startSession();
            }}
            loading={loading}
          >
            重新开始
          </Button>
        </Space>
      </div>
    </Modal>
  );
};

export default WeiboLoginPanel;
