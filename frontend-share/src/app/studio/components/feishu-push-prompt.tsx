"use client";

import { useCallback, useState } from 'react';
import { Button, App, Collapse } from 'antd';
import { pushReviewToLark, reportError } from '@/services/api';
import type { DialogResultData } from '@/types/conversation';

type PushState = {
  pushed: boolean;
  error: string | null;
};

const initialPushState: PushState = { pushed: false, error: null };

const shouldShowFeishuPrompt = (result: DialogResultData): boolean => {
  if (!result.review_approved) {
    return false;
  }
  const meta = result.lark_notification;
  if (!meta || meta.mode === 'off') {
    return false;
  }
  if (meta.auto_sent) {
    return false;
  }
  return meta.auto_sent === false || meta.mode === 'prompt';
};

const buildPushPayload = (result: DialogResultData) => ({
  title: result.title,
  content: result.content,
  project_id: result.project_id,
  version: result.version,
  version_id: result.version_id,
  image_url: result.image_url,
  review_feedback: result.review_feedback,
  hashtags: result.hashtags,
});

type FeishuPushPromptProps = {
  result: DialogResultData;
};

const FeishuPushPrompt = ({ result }: FeishuPushPromptProps) => {
  const { message } = App.useApp();
  const [pushState, setPushState] = useState<PushState>(initialPushState);
  const [isPushing, setIsPushing] = useState(false);

  const handlePush = useCallback(async () => {
    setIsPushing(true);
    const payload = buildPushPayload(result);
    try {
      await pushReviewToLark(payload);
      message.success('已推送到飞书');
      setPushState({ pushed: true, error: null });
    } catch (error) {
      const detail =
        error instanceof Error ? error.message : '推送失败，请稍后重试';
      reportError(error, 'feishu/pushReview');
      message.error(detail);
      setPushState({ pushed: false, error: detail });
    } finally {
      setIsPushing(false);
    }
  }, [message, result]);

  if (!shouldShowFeishuPrompt(result)) {
    if (result.lark_notification?.auto_sent) {
      return (
        <p className="mt-3 font-body text-sm italic text-gold-dark">
          已通过飞书自动推送审核通过通知。
        </p>
      );
    }
    return null;
  }

  const meta = result.lark_notification;
  const promptText = meta?.prompt ?? '审核已通过。是否推送到飞书？';
  const canPush = meta?.configured;

  return (
    <div className="mt-4 rounded-sm border border-gold/30 bg-canvas/60 p-4">
      <p className="font-body text-sm text-ink">{promptText}</p>

      {meta?.error && (
        <p className="mt-2 font-body text-sm text-burgundy-dark">
          自动推送失败：{meta.error}
        </p>
      )}

      {pushState.error && (
        <p className="mt-2 font-body text-sm text-burgundy-dark">{pushState.error}</p>
      )}

      {pushState.pushed ? (
        <p className="mt-3 font-body text-sm italic text-gold-dark">
          已成功推送到飞书。
        </p>
      ) : (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button
            type="primary"
            size="small"
            loading={isPushing}
            disabled={!canPush}
            className="!font-display !text-xs !uppercase !tracking-wider"
            onClick={() => {
              void handlePush();
            }}
          >
            推送到飞书
          </Button>
          {!canPush && (
            <span className="font-body text-xs italic text-ink-muted">
              飞书未配置，请联系管理员
            </span>
          )}
        </div>
      )}

      {!meta?.configured && (
        <Collapse
          ghost
          className="mt-2 !bg-transparent"
          items={[
            {
              key: 'setup',
              label: (
                <span className="font-body text-xs text-ink-muted">
                  如何配置飞书推送？
                </span>
              ),
              children: (
                <div className="font-body text-xs leading-relaxed text-ink-muted">
                  <p>
                    由运维在 <code>backend/.env</code> 配置 Bot 凭证与
                    <code>LARK_NOTIFY_CHAT_ID</code>。
                  </p>
                  <p className="mt-2">
                    详见 <span className="text-gold-dark">mcp-lark/docs/INTEGRATION.md</span>
                  </p>
                </div>
              ),
            },
          ]}
        />
      )}
    </div>
  );
};

export default FeishuPushPrompt;
