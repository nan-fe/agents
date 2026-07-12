"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import { App, Modal } from 'antd';
import {
  closeWeiboOAuthSession,
  confirmWeiboOAuthSession,
  getWeiboOAuthSessionStatus,
  reportError,
  startWeiboOAuthSession,
  type WeiboOAuthSessionResponse,
} from '@/services/api';

type WeiboOAuthConnectPanelProps = {
  open: boolean;
  userId: string;
  onClose: () => void;
  onConnected: () => void;
};

const WeiboOAuthConnectPanel = ({
  open,
  userId,
  onClose,
  onConnected,
}: WeiboOAuthConnectPanelProps) => {
  const { message } = App.useApp();
  const [session, setSession] = useState<WeiboOAuthSessionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const finishConnect = useCallback(async () => {
    stopPolling();
    if (session?.session_id) {
      await closeWeiboOAuthSession(session.session_id).catch(() => undefined);
    }
    setSession(null);
    setStartError(null);
    onConnected();
    onClose();
    message.success('微博连接成功');
  }, [message, onClose, onConnected, session?.session_id, stopPolling]);

  const handleClose = useCallback(async () => {
    stopPolling();
    if (session?.session_id) {
      await closeWeiboOAuthSession(session.session_id).catch(() => undefined);
    }
    setSession(null);
    setStartError(null);
    onClose();
  }, [onClose, session?.session_id, stopPolling]);

  const startSession = useCallback(async () => {
    if (!userId) {
      return;
    }
    setLoading(true);
    setStartError(null);
    try {
      const data = await startWeiboOAuthSession(userId);
      setSession(data);
      if (data.oauth_completed && data.logged_in) {
        await finishConnect();
      }
    } catch (error) {
      reportError(error, 'social/startWeiboOAuth');
      const detail = error instanceof Error ? error.message : '无法启动微博 OAuth';
      setStartError(detail);
      message.error(detail);
    } finally {
      setLoading(false);
    }
  }, [finishConnect, message, userId]);

  useEffect(() => {
    if (!open) {
      stopPolling();
      return;
    }
    void startSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, userId]);

  useEffect(() => {
    if (!open || !session?.session_id || session.oauth_completed) {
      stopPolling();
      return undefined;
    }
    pollRef.current = window.setInterval(() => {
      void getWeiboOAuthSessionStatus(session.session_id)
        .then((data) => {
          setSession(data);
          if (data.oauth_error) {
            setStartError(data.oauth_error);
            stopPolling();
          }
        })
        .catch((error) => {
          reportError(error, 'social/pollWeiboOAuthSession');
        });
    }, 1500);
    return () => {
      stopPolling();
    };
  }, [open, session?.oauth_completed, session?.session_id, stopPolling]);

  const handleConfirm = useCallback(async () => {
    if (!session?.session_id || confirming) {
      return;
    }
    setConfirming(true);
    try {
      await confirmWeiboOAuthSession(session.session_id);
      setSession(null);
      setStartError(null);
      stopPolling();
      onConnected();
      onClose();
      message.success('微博连接成功');
    } catch (error) {
      reportError(error, 'social/confirmWeiboOAuth');
      const detail = error instanceof Error ? error.message : '尚未完成授权';
      message.warning(detail);
    } finally {
      setConfirming(false);
    }
  }, [confirming, message, onClose, onConnected, session?.session_id, stopPolling]);

  const waiting = loading || (session != null && !startError && !session.oauth_completed);

  return (
    <Modal
      open={open}
      title={null}
      footer={null}
      closable={!loading && !confirming}
      mask={{ closable: !loading && !confirming }}
      onCancel={() => {
        void handleClose();
      }}
      width={480}
      centered
      destroyOnHidden
      className="weibo-sync-modal weibo-login-modal"
    >
      <div className="weibo-sync-modal__panel">
        <span className="weibo-sync-modal__corner weibo-sync-modal__corner--tl" aria-hidden="true" />
        <span className="weibo-sync-modal__corner weibo-sync-modal__corner--br" aria-hidden="true" />

        <p className="weibo-sync-modal__eyebrow">Weibo OAuth</p>
        <h2 className="weibo-sync-modal__title">
          {startError ? '无法连接微博' : waiting ? '完成微博授权' : '连接微博'}
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
            {waiting ? (
              <div className="weibo-sync-modal__pulse" aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
            ) : null}
            <p className="weibo-sync-modal__hint">
              已打开微博 Profile 浏览器并完成 OAuth 授权页。请在浏览器中登录微博并授权应用，
              成功后点击下方「我已完成授权」。发帖将通过浏览器模拟完成。
            </p>
            {session?.weibo_screen_name ? (
              <p className="weibo-sync-modal__hint text-gold-dark">
                检测到账号 @{session.weibo_screen_name}
              </p>
            ) : null}
            {session?.profile_path ? (
              <p className="weibo-sync-modal__hint text-ink-muted/70">
                Profile 路径：<code>{session.profile_path}</code>
              </p>
            ) : null}
            <div className="weibo-sync-modal__actions">
              <button
                type="button"
                className="weibo-sync-modal__btn weibo-sync-modal__btn--ghost"
                disabled={loading || confirming}
                onClick={() => {
                  void handleClose();
                }}
              >
                取消
              </button>
              <button
                type="button"
                className="weibo-sync-modal__btn weibo-sync-modal__btn--primary"
                disabled={!session?.session_id || loading || confirming}
                onClick={() => {
                  void handleConfirm();
                }}
              >
                {confirming ? '确认中…' : '我已完成授权'}
              </button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};

export default WeiboOAuthConnectPanel;
