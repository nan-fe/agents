"use client";

import { useCallback, useEffect, useState } from 'react';
import { App, Modal } from 'antd';
import {
  closeWeiboLoginSession,
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

const WeiboLoginPanel = ({ open, onClose, onLoggedIn }: WeiboLoginPanelProps) => {
  const { message } = App.useApp();
  const [session, setSession] = useState<WeiboLoginStartResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

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

  const waiting = loading || (session != null && !startError);

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
      width={440}
      centered
      destroyOnHidden
      className="weibo-sync-modal weibo-login-modal"
    >
      <div className="weibo-sync-modal__panel">
        <span className="weibo-sync-modal__corner weibo-sync-modal__corner--tl" aria-hidden="true" />
        <span className="weibo-sync-modal__corner weibo-sync-modal__corner--br" aria-hidden="true" />

        <p className="weibo-sync-modal__eyebrow">Weibo</p>
        <h2 className="weibo-sync-modal__title">
          {startError ? '无法打开微博' : waiting ? '等待登录完成' : '微博登录'}
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
            <div className="weibo-sync-modal__pulse" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <button
              type="button"
              className="weibo-sync-modal__btn weibo-sync-modal__btn--ghost weibo-login-modal__cancel"
              disabled={loading}
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
