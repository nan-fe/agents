"use client";

import { useCallback, useEffect, useState } from 'react';
import { App, Modal } from 'antd';
import {
  clickWeiboLogin,
  closeWeiboLoginSession,
  getWeiboLoginScreenshotUrl,
  reportError,
  startWeiboLoginSession,
  type WeiboLoginStartResponse,
  pollWeiboLoginStatus,
} from '@/services/api';

type WeiboLoginPanelProps = {
  open: boolean;
  onClose: () => void;
  onLoggedIn: () => void;
};

const POLL_INTERVAL_MS = 5000;
const SCREENSHOT_REFRESH_MS = 1500;

const WeiboLoginPanel = ({ open, onClose, onLoggedIn }: WeiboLoginPanelProps) => {
  const { message } = App.useApp();
  const [session, setSession] = useState<WeiboLoginStartResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [screenshotTick, setScreenshotTick] = useState(0);
  const [clicking, setClicking] = useState(false);

  const finishLogin = useCallback(async () => {
    if (session?.session_id) {
      await closeWeiboLoginSession(session.session_id).catch(() => undefined);
    }
    setSession(null);
    setStartError(null);
    onLoggedIn();
    onClose();
    message.success('微博登录成功');
  }, [message, onClose, onLoggedIn, session?.session_id]);

  const handleClose = useCallback(async () => {
    if (session?.session_id) {
      await closeWeiboLoginSession(session.session_id).catch(() => undefined);
    }
    setSession(null);
    setStartError(null);
    onClose();
  }, [onClose, session?.session_id]);

  const startSession = useCallback(async () => {
    setLoading(true);
    setStartError(null);
    try {
      const data = await startWeiboLoginSession();
      if (data.logged_in) {
        await finishLogin();
        return;
      }
      setSession(data);
      setScreenshotTick((tick) => tick + 1);
    } catch (error) {
      reportError(error, 'social/startWeiboLogin');
      const detail = error instanceof Error ? error.message : '无法启动微博登录';
      setStartError(detail);
      message.error(detail);
    } finally {
      setLoading(false);
    }
  }, [finishLogin, message]);

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
        if (status.logged_in) {
          window.clearInterval(interval);
          await finishLogin();
        }
      } catch {
        // 会话过期时静默停止轮询
      }
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(interval);
  }, [finishLogin, open, session?.session_id]);

  useEffect(() => {
    if (!open || !session?.session_id || startError) {
      return undefined;
    }

    const interval = window.setInterval(() => {
      setScreenshotTick((tick) => tick + 1);
    }, SCREENSHOT_REFRESH_MS);

    return () => window.clearInterval(interval);
  }, [open, session?.session_id, startError]);

  const handleScreenshotClick = useCallback(
    async (event: React.MouseEvent<HTMLImageElement>) => {
      if (!session?.session_id || clicking) {
        return;
      }

      const img = event.currentTarget;
      const rect = img.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) {
        return;
      }

      const scaleX = session.viewport_width / rect.width;
      const scaleY = session.viewport_height / rect.height;
      const x = (event.clientX - rect.left) * scaleX;
      const y = (event.clientY - rect.top) * scaleY;

      setClicking(true);
      try {
        const result = await clickWeiboLogin(session.session_id, x, y);
        setScreenshotTick((tick) => tick + 1);
        if (result.logged_in) {
          await finishLogin();
        }
      } catch (error) {
        reportError(error, 'social/clickWeiboLogin');
      } finally {
        setClicking(false);
      }
    },
    [clicking, finishLogin, session],
  );

  const waiting = loading || (session != null && !startError);
  const screenshotUrl =
    session?.session_id != null
      ? getWeiboLoginScreenshotUrl(session.session_id, screenshotTick)
      : null;

  return (
    <Modal
      open={open}
      title={null}
      footer={null}
      closable={!loading}
      mask={{ closable: !loading }}
      onCancel={() => {
        void handleClose();
      }}
      width={session && !startError ? 720 : 440}
      centered
      destroyOnHidden
      className="weibo-sync-modal weibo-login-modal"
    >
      <div className="weibo-sync-modal__panel">
        <span className="weibo-sync-modal__corner weibo-sync-modal__corner--tl" aria-hidden="true" />
        <span className="weibo-sync-modal__corner weibo-sync-modal__corner--br" aria-hidden="true" />

        <p className="weibo-sync-modal__eyebrow">Weibo</p>
        <h2 className="weibo-sync-modal__title">
          {startError ? '无法打开微博' : waiting ? '完成微博登录' : '微博登录'}
        </h2>

        {startError ? (
          <>
            <p className="weibo-sync-modal__hint">{startError}</p>
            <div className="weibo-sync-modal__actions">
              <button
                type="button"
                className="weibo-sync-modal__btn weibo-sync-modal__btn--ghost"
                onClick={() => {
                  void handleClose();
                }}
              >
                关闭
              </button>
              <button
                type="button"
                className="weibo-sync-modal__btn weibo-sync-modal__btn--primary"
                onClick={() => {
                  void startSession();
                }}
              >
                重试
              </button>
            </div>
          </>
        ) : (
          <div className="weibo-login-modal__waiting">
            {screenshotUrl ? (
              <>
                <p className="weibo-sync-modal__hint">
                  在下方页面中点击输入账号密码或扫码，登录成功后会自动关闭
                </p>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={screenshotUrl}
                  alt="微博登录页面"
                  className="weibo-login-modal__screenshot"
                  onClick={(event) => {
                    void handleScreenshotClick(event);
                  }}
                />
              </>
            ) : (
              <div className="weibo-sync-modal__pulse" aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
            )}
            <button
              type="button"
              className="weibo-sync-modal__btn weibo-sync-modal__btn--ghost weibo-login-modal__cancel"
              disabled={loading || clicking}
              onClick={() => {
                void handleClose();
              }}
            >
              取消
            </button>
          </div>
        )}
      </div>
    </Modal>
  );
};

export default WeiboLoginPanel;
