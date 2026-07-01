"use client";

import { Modal } from 'antd';
import type { PublishJobResponse } from '@/services/api';

type WeiboShareSyncModalProps = {
  open: boolean;
  phase: 'confirm' | 'publishing';
  publishJob: PublishJobResponse | null;
  onConfirm: () => void;
  onShareOnly: () => void;
  onCancel: () => void;
};

const WeiboShareSyncModal = ({
  open,
  phase,
  publishJob,
  onConfirm,
  onShareOnly,
  onCancel,
}: WeiboShareSyncModalProps) => {
  const isPublishing = phase === 'publishing';

  return (
    <Modal
      open={open}
      title={null}
      footer={null}
      closable={!isPublishing}
      mask={{ closable: !isPublishing }}
      onCancel={onCancel}
      width={440}
      centered
      destroyOnHidden
      className="weibo-sync-modal"
    >
      <div className="weibo-sync-modal__panel">
        <span className="weibo-sync-modal__corner weibo-sync-modal__corner--tl" aria-hidden="true" />
        <span className="weibo-sync-modal__corner weibo-sync-modal__corner--br" aria-hidden="true" />

        <p className="weibo-sync-modal__eyebrow">Publish</p>
        <h2 className="weibo-sync-modal__title">
          {isPublishing ? '正在同步至微博' : '是否需要同步发布到微博？'}
        </h2>

        {isPublishing ? (
          <div className="weibo-sync-modal__progress">
            <p className="weibo-sync-modal__hint">
              发布完成后将自动生成分享链接并复制到剪贴板
            </p>
            <div className="weibo-sync-modal__pulse" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            {publishJob && publishJob.progress.length > 0 && (
              <ul className="weibo-sync-modal__log">
                {publishJob.progress.slice(-5).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <>
            <p className="weibo-sync-modal__hint">
              确认后将先完成微博发布，再为你生成分享链接。
            </p>
            <div className="weibo-sync-modal__actions">
              <button
                type="button"
                className="weibo-sync-modal__btn weibo-sync-modal__btn--ghost"
                onClick={onShareOnly}
              >
                仅生成链接
              </button>
              <button
                type="button"
                className="weibo-sync-modal__btn weibo-sync-modal__btn--primary"
                onClick={onConfirm}
              >
                确认发布
              </button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
};

export default WeiboShareSyncModal;
