"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import { App, Modal } from 'antd';
import {
  closeXOAuthSession,
  confirmXOAuthSession,
  getXOAuthSessionStatus,
  reportError,
  startXOAuthSession,
  type XOAuthSessionResponse,
} from '@/services/api';

type XOAuthConnectPanelProps = {
  open: boolean;
  userId: string;
  onClose: () => void;
  onConnected: () => void;
};

const XOAuthConnectPanel = ({
  open,
  userId,
  onClose,
  onConnected,
}: XOAuthConnectPanelProps) => {
  const { message } = App.useApp();
  const [session, setSession] = useState<XOAuthSessionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);
  const authorizeOpenedRef = useRef(false);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const finishConnect = useCallback(async () => {
    stopPolling();
    if (session?.session_id) {
      await closeXOAuthSession(session.session_id).catch(() => undefined);
    }
    setSession(null);
    setStartError(null);
    authorizeOpenedRef.current = false;
    onConnected();
    onClose();
    message.success('X 连接成功');
  }, [message, onClose, onConnected, session?.session_id, stopPolling]);

  const handleClose = useCallback(async () => {
    stopPolling();
    if (session?.session_id) {
      await closeXOAuthSession(session.session_id).catch(() => undefined);
    }
    setSession(null);
    setStartError(null);
    authorizeOpenedRef.current = false;
    onClose();
  }, [onClose, session?.session_id, stopPolling]);

  const openAuthorizeUrl = useCallback((url: string) => {
    window.open(url, '_blank', 'noopener,noreferrer');
  }, []);

  const startSession = useCallback(async () => {
    if (!userId) {
      return;
    }
    setLoading(true);
    setStartError(null);
    try {
      const data = await startXOAuthSession(userId);
      setSession(data);
      if (data.browserless && data.authorize_url && !authorizeOpenedRef.current) {
        authorizeOpenedRef.current = true;
        openAuthorizeUrl(data.authorize_url);
      }
      if (data.oauth_completed && data.logged_in) {
        await finishConnect();
      }
    } catch (error) {
      reportError(error, 'social/startXOAuth');
      const detail = error instanceof Error ? error.message : '无法启动 X OAuth';
      setStartError(detail);
      message.error(detail);
    } finally {
      setLoading(false);
    }
  }, [finishConnect, message, openAuthorizeUrl, userId]);

  useEffect(() => {
    if (!open) {
      stopPolling();
      authorizeOpenedRef.current = false;
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
      void getXOAuthSessionStatus(session.session_id)
        .then((data) => {
          setSession(data);
          if (data.oauth_error) {
            setStartError(data.oauth_error);
            stopPolling();
          }
        })
        .catch((error) => {
          reportError(error, 'social/pollXOAuthSession');
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
      await confirmXOAuthSession(session.session_id);
      setSession(null);
      setStartError(null);
      stopPolling();
      onConnected();
      onClose();
      message.success('X 连接成功');
    } catch (error) {
      reportError(error, 'social/confirmXOAuth');
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

        <p className="weibo-sync-modal__eyebrow">X OAuth</p>
        <h2 className="weibo-sync-modal__title">
          {startError ? '无法连接 X' : waiting ? '完成 X 授权' : '连接 X'}
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
              {session?.browserless
                ? '请点击下方按钮在新标签页登录 X 并授权应用，完成后返回点击「我已完成授权」。发帖将通过服务器浏览器模拟完成。'
                : '已打开 X Profile 浏览器并完成 OAuth 授权页。请在浏览器中登录 X 并授权应用，成功后点击下方「我已完成授权」。发帖将通过浏览器模拟完成，不消耗 X API Credits。'}
            </p>
            {session?.browserless && session.authorize_url ? (
              <div className="weibo-sync-modal__actions">
                <button
                  type="button"
                  className="weibo-sync-modal__btn weibo-sync-modal__btn--ghost"
                  disabled={loading || confirming}
                  onClick={() => {
                    openAuthorizeUrl(session.authorize_url!);
                  }}
                >
                  打开 X 授权页
                </button>
              </div>
            ) : null}
            {session?.x_username ? (
              <p className="weibo-sync-modal__hint text-gold-dark">
                检测到账号 @{session.x_username}
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

export default XOAuthConnectPanel;
