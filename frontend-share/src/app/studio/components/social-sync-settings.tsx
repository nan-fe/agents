"use client";

import { startTransition, useActionState, useCallback, useEffect, useState } from 'react';
import { useSession } from 'next-auth/react';
import { Button, App, Collapse } from 'antd';
import {
  disconnectXOAuth,
  getSocialStatus,
  getXOAuthUserStatus,
  reportError,
  triggerXSyncOnce,
  type SocialStatusResponse,
  type XOAuthUserStatus,
} from '@/services/api';
import WeiboLoginPanel from '@/app/studio/components/weibo-login-panel';
import XLoginPanel from '@/app/studio/components/x-login-panel';
import XOAuthConnectPanel from '@/app/studio/components/x-oauth-connect-panel';
import { getStudioUserId } from '@/app/studio/lib/studio-user';

type SyncActionState = {
  message: string | null;
  error: string | null;
};

const initialSyncState: SyncActionState = { message: null, error: null };

const syncAction = (
  messageApi: ReturnType<typeof App.useApp>['message'],
) => async (
  _prev: SyncActionState,
  _payload: null,
): Promise<SyncActionState> => {
  try {
    const result = await triggerXSyncOnce();
    const text = result.synced
      ? '已触发 X 同步任务'
      : String(result.reason || result.error || '同步已跳过');
    messageApi.success(text);
    return { message: text, error: null };
  } catch (error) {
    const detail = error instanceof Error ? error.message : '同步失败';
    reportError(error, 'social/triggerXSync');
    messageApi.error(detail);
    return { message: null, error: detail };
  }
};

const SocialSyncSettings = () => {
  const { message } = App.useApp();
  const { data: session } = useSession();
  const userId = getStudioUserId(session);
  const [status, setStatus] = useState<SocialStatusResponse | null>(null);
  const [xOAuthStatus, setXOAuthStatus] = useState<XOAuthUserStatus | null>(null);
  const [weiboLoginOpen, setWeiboLoginOpen] = useState(false);
  const [xOAuthOpen, setXOAuthOpen] = useState(false);
  const [xLoginOpen, setXLoginOpen] = useState(false);
  const [syncState, runSync, isSyncing] = useActionState(
    syncAction(message),
    initialSyncState,
  );

  const refreshStatus = useCallback(async (forceRefresh = false) => {
    try {
      const data = await getSocialStatus(forceRefresh, userId || undefined);
      setStatus(data);
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

  const weiboReady =
    status.weibo.configured && (status.weibo.logged_in || status.dry_run);
  const xReady = Boolean(
    status.x_dry_run ||
      (status.x_oauth_configured
        ? xOAuthStatus?.connected
        : status.x?.logged_in || xOAuthStatus?.connected),
  );

  const handleConnectX = () => {
    if (status?.x_oauth_configured) {
      setXOAuthOpen(true);
      return;
    }
    setXLoginOpen(true);
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
      <WeiboLoginPanel
        open={weiboLoginOpen}
        onClose={() => setWeiboLoginOpen(false)}
        onLoggedIn={() => {
          void refreshStatus(true);
        }}
      />
      {userId && (
        <>
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
      {status.weibo_publish_enabled && (
        <Button
          block
          size="small"
          className="!font-display !text-xs"
          onClick={() => setWeiboLoginOpen(true)}
        >
          {weiboReady ? '微博已登录' : '登录微博'}
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
      <div className="rounded-sm border border-gold/20 bg-canvas/40 p-2">
      <Collapse
        ghost
        className="!bg-transparent"
        items={[
          {
            key: 'social',
            label: (
              <span className="font-body text-xs text-ink-muted">
                社交媒体发布设置
              </span>
            ),
            children: (
              <div className="space-y-3 font-body text-xs leading-relaxed text-ink-muted">
                <p>
                  微博发布：
                  {status.weibo_publish_enabled
                    ? weiboReady
                      ? ' 已登录，可自动发布'
                      : ` 未就绪（${status.weibo.reason || '请登录微博'}）`
                    : ' 未启用'}
                </p>
                <p>
                  X 发布：
                  {status.x_publish_enabled
                    ? xReady
                      ? ' 已连接，通过浏览器发布（免 API Credits）'
                      : ' 未就绪（请连接 X 账号）'
                    : ' 未启用'}
                </p>
                <p>
                  X 自动同步：
                  {status.x_sync_enabled
                    ? ` 监听 @${status.x_sync_username || '未配置'}，每 ${status.x_sync_interval_seconds}s 轮询`
                    : ' 未启用'}
                </p>
                {status.x_sync_enabled && (
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      size="small"
                      loading={isSyncing}
                      className="!font-display !text-xs"
                      onClick={() => {
                        startTransition(() => {
                          runSync(null);
                        });
                      }}
                    >
                      立即同步 X
                    </Button>
                    {syncState.message && (
                      <span className="text-gold-dark">{syncState.message}</span>
                    )}
                    {syncState.error && (
                      <span className="text-burgundy-dark">{syncState.error}</span>
                    )}
                  </div>
                )}
                <p className="text-ink-muted/80">
                  X 连接会在 Profile 浏览器内完成 OAuth 授权；发帖模拟人工操作，不走 X 付费 API。
                </p>
              </div>
            ),
          },
        ]}
      />
      </div>
    </div>
  );
};

export default SocialSyncSettings;
