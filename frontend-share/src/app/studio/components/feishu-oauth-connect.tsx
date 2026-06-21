"use client";

import { useEffect, useState } from 'react';
import { Button, App } from 'antd';
import {
  disconnectLarkOAuth,
  getLarkOAuthUserStatus,
  reportError,
  startLarkOAuthAuthorizeUrl,
} from '@/services/api';

type FeishuOAuthConnectProps = {
  userId: string;
  onStatusChange?: (connected: boolean) => void;
  variant?: 'default' | 'compact';
};

const FeishuOAuthConnect = ({
  userId,
  onStatusChange,
  variant = 'default',
}: FeishuOAuthConnectProps) => {
  const { message } = App.useApp();
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [disconnecting, setDisconnecting] = useState(false);

  const refreshStatus = async () => {
    if (!userId) {
      setConnected(false);
      setLoading(false);
      return;
    }
    try {
      const status = await getLarkOAuthUserStatus(userId);
      setConnected(Boolean(status.connected));
      onStatusChange?.(Boolean(status.connected));
    } catch (error) {
      reportError(error, 'lark/oauthUserStatus');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refreshStatus();
  }, [userId]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('lark_oauth') === 'connected') {
      message.success('飞书授权成功');
      params.delete('lark_oauth');
      const next = `${window.location.pathname}${params.toString() ? `?${params}` : ''}`;
      window.history.replaceState({}, '', next);
      void refreshStatus();
    }
  }, []);

  if (!userId) {
    return null;
  }

  if (loading) {
    return (
      <p className="font-body text-xs italic text-ink-muted">正在检查飞书授权状态…</p>
    );
  }

  if (connected) {
    if (variant === 'compact') {
      return (
        <span className="font-body text-xs text-gold-dark">飞书已连接</span>
      );
    }
    return (
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-body text-sm text-gold-dark">已连接飞书账号</span>
        <Button
          type="link"
          size="small"
          loading={disconnecting}
          className="!h-auto !p-0 !font-body !text-sm !italic"
          onClick={() => {
            setDisconnecting(true);
            void disconnectLarkOAuth(userId)
              .then(() => {
                message.info('已解除飞书连接');
                setConnected(false);
                onStatusChange?.(false);
              })
              .catch((error) => {
                reportError(error, 'lark/oauthDisconnect');
                message.error('解除连接失败');
              })
              .finally(() => setDisconnecting(false));
          }}
        >
          解除连接
        </Button>
      </div>
    );
  }

  if (variant === 'compact') {
    return (
      <Button
        type="default"
        size="small"
        className="!font-display !text-xs !uppercase !tracking-wider"
        onClick={() => {
          const returnUrl = window.location.href.split('?')[0].split('#')[0];
          window.location.assign(
            startLarkOAuthAuthorizeUrl({
              userId,
              returnUrl,
            }),
          );
        }}
      >
        连接飞书
      </Button>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="font-body text-sm text-ink-muted">
        推送前需授权飞书：将自动打开飞书授权页，同意后即可以个人身份发消息。
      </p>
      <Button
        type="default"
        size="small"
        className="!font-display !text-xs !uppercase !tracking-wider"
        onClick={() => {
          const returnUrl = window.location.href.split('?')[0].split('#')[0];
          window.location.assign(
            startLarkOAuthAuthorizeUrl({
              userId,
              returnUrl,
            }),
          );
        }}
      >
        连接飞书账号
      </Button>
    </div>
  );
};

export default FeishuOAuthConnect;
