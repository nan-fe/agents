"use client";

import { startTransition, useActionState, useEffect, useState } from 'react';
import { Button, App, Collapse } from 'antd';
import {
  getSocialStatus,
  reportError,
  triggerXSyncOnce,
  type SocialStatusResponse,
} from '@/services/api';

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
  const [status, setStatus] = useState<SocialStatusResponse | null>(null);
  const [syncState, runSync, isSyncing] = useActionState(
    syncAction(message),
    initialSyncState,
  );

  useEffect(() => {
    let cancelled = false;
    getSocialStatus()
      .then((data) => {
        if (!cancelled) {
          setStatus(data);
        }
      })
      .catch((error) => {
        reportError(error, 'social/getSocialStatus');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!status?.x_sync_enabled && !status?.weibo_publish_enabled) {
    return null;
  }

  const weiboReady =
    status.weibo.configured && (status.weibo.logged_in || status.dry_run);

  return (
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
                      ? ' 已配置'
                      : ` 未就绪（${status.weibo.reason || '请登录微博 Profile'}）`
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
                  在 <code>backend/.env</code> 配置{' '}
                  <code>WEIBO_PUBLISH_ENABLED</code>、
                  <code>BROWSER_USE_PROFILE_PATH</code> 与{' '}
                  <code>X_SYNC_*</code>。首次需用该 Profile 手动登录微博/X。
                </p>
              </div>
            ),
          },
        ]}
      />
    </div>
  );
};

export default SocialSyncSettings;
