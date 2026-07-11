"use client";

import { Modal } from 'antd';
import type { PublishJobResponse } from '@/services/api';

export type SocialPublishPlatform = 'weibo' | 'x';

type SocialShareSyncModalProps = {
  open: boolean;
  phase: 'choose' | 'confirm' | 'publishing';
  platform: SocialPublishPlatform;
  publishJob: PublishJobResponse | null;
  showWeibo?: boolean;
  showX?: boolean;
  onSelectPlatform?: (platform: SocialPublishPlatform) => void;
  onConfirm: () => void;
  onShareOnly: () => void;
  onCancel: () => void;
};

const PLATFORM_LABEL: Record<SocialPublishPlatform, string> = {
  weibo: '微博',
  x: 'X',
};

const SocialShareSyncModal = ({
  open,
  phase,
  platform,
  publishJob,
  showWeibo = true,
  showX = true,
  onSelectPlatform,
  onConfirm,
  onShareOnly,
  onCancel,
}: SocialShareSyncModalProps) => {
  const isPublishing = phase === 'publishing';
  const label = PLATFORM_LABEL[platform];

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
          {phase === 'choose'
            ? '选择发布平台'
            : isPublishing
              ? `正在同步至${label}`
              : `是否需要同步发布到${label}？`}
        </h2>

        {phase === 'choose' ? (
          <>
            <p className="weibo-sync-modal__hint">
              选择平台后将先完成社交发布，再为你生成分享链接。
            </p>
            <div className="weibo-sync-modal__actions weibo-sync-modal__actions--stack">
              {showWeibo && (
                <button
                  type="button"
                  className="weibo-sync-modal__btn weibo-sync-modal__btn--primary"
                  onClick={() => onSelectPlatform?.('weibo')}
                >
                  发布到微博
                </button>
              )}
              {showX && (
                <button
                  type="button"
                  className="weibo-sync-modal__btn weibo-sync-modal__btn--primary"
                  onClick={() => onSelectPlatform?.('x')}
                >
                  发布到 X
                </button>
              )}
              <button
                type="button"
                className="weibo-sync-modal__btn weibo-sync-modal__btn--ghost"
                onClick={onShareOnly}
              >
                仅生成链接
              </button>
            </div>
          </>
        ) : isPublishing ? (
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
              确认后将先完成{label}发布，再为你生成分享链接。
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

export default SocialShareSyncModal;
