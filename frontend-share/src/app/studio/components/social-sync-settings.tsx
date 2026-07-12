"use client";

import { useCallback, useEffect, useState } from 'react';
import { useSession } from 'next-auth/react';
import { Button, App } from 'antd';
import {
  disconnectWeiboOAuth,
  disconnectXOAuth,
  getSocialStatus,
  getWeiboOAuthUserStatus,
  getXOAuthUserStatus,
  reportError,
  type SocialStatusResponse,
  type WeiboOAuthUserStatus,
  type XOAuthUserStatus,
} from '@/services/api';
import WeiboLoginPanel from '@/app/studio/components/weibo-login-panel';
import WeiboOAuthConnectPanel from '@/app/studio/components/weibo-oauth-connect-panel';
import XLoginPanel from '@/app/studio/components/x-login-panel';
import XOAuthConnectPanel from '@/app/studio/components/x-oauth-connect-panel';
import { getStudioUserId } from '@/app/studio/lib/studio-user';

const SocialSyncSettings = () => {
  const { message } = App.useApp();
  const { data: session } = useSession();
  const userId = getStudioUserId(session);
  const [status, setStatus] = useState<SocialStatusResponse | null>(null);
  const [weiboOAuthStatus, setWeiboOAuthStatus] = useState<WeiboOAuthUserStatus | null>(null);
  const [xOAuthStatus, setXOAuthStatus] = useState<XOAuthUserStatus | null>(null);
  const [weiboOAuthOpen, setWeiboOAuthOpen] = useState(false);
  const [weiboLoginOpen, setWeiboLoginOpen] = useState(false);
  const [xOAuthOpen, setXOAuthOpen] = useState(false);
  const [xLoginOpen, setXLoginOpen] = useState(false);

  const refreshStatus = useCallback(async (forceRefresh = false) => {
    try {
      const data = await getSocialStatus(forceRefresh, userId || undefined);
      setStatus(data);
      if (userId && data.weibo_publish_enabled) {
        const weiboOauth = await getWeiboOAuthUserStatus(userId, forceRefresh);
        setWeiboOAuthStatus(weiboOauth);
      } else {
        setWeiboOAuthStatus(null);
      }
      if (userId && data.x_publish_enabled) {
        const oauth = await getXOAuthUserStatus(userId, forceRefresh);
        setXOAuthStatus(oauth);
      } else {
        setXOAuthStatus(null);
      }
    } catch (error) {
      reportError(error, 'social/getSocialStatus');
    }
  }, [userId]);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  if (
    !status?.x_sync_enabled &&
    !status?.weibo_publish_enabled &&
    !status?.x_publish_enabled
  ) {
    return null;
  }

  const weiboReady = Boolean(
    status.weibo.configured &&
      (status.dry_run ||
        (status.weibo_oauth_configured
          ? weiboOAuthStatus?.connected
          : status.weibo.logged_in || weiboOAuthStatus?.connected)),
  );
  const xReady = Boolean(
    status.x_dry_run ||
      (status.x_oauth_configured
        ? xOAuthStatus?.connected
        : status.x?.logged_in || xOAuthStatus?.connected),
  );

  const handleConnectWeibo = () => {
    if (status?.weibo_oauth_configured) {
      setWeiboOAuthOpen(true);
      return;
    }
    setWeiboLoginOpen(true);
  };

  const handleConnectX = () => {
    if (status?.x_oauth_configured) {
      setXOAuthOpen(true);
      return;
    }
    setXLoginOpen(true);
  };

  const handleDisconnectWeibo = () => {
    if (!userId) {
      return;
    }
    void disconnectWeiboOAuth(userId)
      .then(() => {
        message.info('已解除微博连接');
        void refreshStatus(true);
      })
      .catch((error) => {
        reportError(error, 'social/weiboOAuthDisconnect');
        message.error('解除连接失败');
      });
  };

  const handleDisconnectX = () => {
    if (!userId) {
      return;
    }
    void disconnectXOAuth(userId)
      .then(() => {
        message.info('已解除 X 连接');
        void refreshStatus(true);
      })
      .catch((error) => {
        reportError(error, 'social/xOAuthDisconnect');
        message.error('解除连接失败');
      });
  };

  return (
    <div className="space-y-2">
      {userId && (
        <>
          <WeiboOAuthConnectPanel
            open={weiboOAuthOpen}
            userId={userId}
            onClose={() => setWeiboOAuthOpen(false)}
            onConnected={() => {
              void refreshStatus(true);
            }}
          />
          <WeiboLoginPanel
            open={weiboLoginOpen}
            userId={userId}
            onClose={() => setWeiboLoginOpen(false)}
            onLoggedIn={() => {
              void refreshStatus(true);
            }}
          />
          <XOAuthConnectPanel
            open={xOAuthOpen}
            userId={userId}
            onClose={() => setXOAuthOpen(false)}
            onConnected={() => {
              void refreshStatus(true);
            }}
          />
          <XLoginPanel
            open={xLoginOpen}
            userId={userId}
            onClose={() => setXLoginOpen(false)}
            onLoggedIn={() => {
              void refreshStatus(true);
            }}
          />
        </>
      )}
      {status.weibo_publish_enabled && userId && (
        <Button
          block
          size="small"
          className="!font-display !text-xs"
          onClick={handleConnectWeibo}
        >
          {weiboReady
            ? `微博已连接${weiboOAuthStatus?.weibo_screen_name ? ` (@${weiboOAuthStatus.weibo_screen_name})` : ''}`
            : '连接微博'}
        </Button>
      )}
      {weiboReady && userId && (
        <Button
          block
          size="small"
          type="link"
          className="!font-display !text-xs"
          onClick={handleDisconnectWeibo}
        >
          解除微博连接
        </Button>
      )}
      {status.x_publish_enabled && userId && (
        <Button
          block
          size="small"
          className="!font-display !text-xs"
          onClick={handleConnectX}
        >
          {xReady
            ? `X 已连接${xOAuthStatus?.x_username ? ` (@${xOAuthStatus.x_username})` : ''}`
            : '连接 X'}
        </Button>
      )}
      {xReady && userId && (
        <Button
          block
          size="small"
          type="link"
          className="!font-display !text-xs"
          onClick={handleDisconnectX}
        >
          解除 X 连接
        </Button>
      )}
    </div>
  );
};

export default SocialSyncSettings;
