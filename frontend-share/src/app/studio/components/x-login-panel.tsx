"use client";

import { useCallback, useEffect, useState } from 'react';
import { App, Modal } from 'antd';
import {
  closeXLoginSession,
  confirmXLogin,
  reportError,
  startXLoginSession,
  type WeiboLoginStartResponse,
} from '@/services/api';

type XLoginPanelProps = {
  open: boolean;
  userId: string;
  onClose: () => void;
  onLoggedIn: () => void;
};

const XLoginPanel = ({ open, userId, onClose, onLoggedIn }: XLoginPanelProps) => {
  const { message } = App.useApp();
  const [session, setSession] = useState<WeiboLoginStartResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const finishLogin = useCallback(async () => {
    if (session?.session_id) {
      await closeXLoginSession(session.session_id).catch(() => undefined);
    }
    setSession(null);
    setStartError(null);
    onLoggedIn();
    onClose();
    message.success('X 登录成功');
  }, [message, onClose, onLoggedIn, session?.session_id]);

  const handleClose = useCallback(async () => {
    if (session?.session_id) {
      await closeXLoginSession(session.session_id).catch(() => undefined);
    }
    setSession(null);
    setStartError(null);
    onClose();
  }, [onClose, session?.session_id]);

  const startSession = useCallback(async () => {
    if (!userId) {
      return;
    }
    setLoading(true);
    setStartError(null);
    try {
      const data = await startXLoginSession(userId);
      if (data.logged_in) {
        await finishLogin();
        return;
      }
      setSession(data);
    } catch (error) {
      reportError(error, 'social/startXLogin');
      const detail = error instanceof Error ? error.message : '无法启动 X 登录';
      setStartError(detail);
      message.error(detail);
    } finally {
      setLoading(false);
    }
  }, [finishLogin, message, userId]);

  useEffect(() => {
    if (!open || !userId) {
      return;
    }
    void startSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, userId]);

  const handleConfirm = useCallback(async () => {
    if (!session?.session_id || confirming) {
      return;
    }
    setConfirming(true);
    try {
      await confirmXLogin(session.session_id);
      setSession(null);
      setStartError(null);
      onLoggedIn();
      onClose();
      message.success('X 登录成功');
    } catch (error) {
      reportError(error, 'social/confirmXLogin');
      const detail = error instanceof Error ? error.message : '尚未检测到登录';
      message.warning(detail);
    } finally {
      setConfirming(false);
    }
  }, [confirming, message, onClose, onLoggedIn, session?.session_id]);

  const waiting = loading || (session != null && !startError);

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

        <p className="weibo-sync-modal__eyebrow">X</p>
        <h2 className="weibo-sync-modal__title">
          {startError ? '无法打开 X' : waiting ? '完成 X 登录' : 'X 登录'}
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
              已为你打开 X Profile 浏览器窗口。请在浏览器中完成账号登录，成功后点击下方「我已登录」保存登录态。
            </p>
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
                {confirming ? '检测中…' : '我已登录'}
              </button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};

export default XLoginPanel;
