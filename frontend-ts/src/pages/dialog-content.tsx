import {
  useState,
  useRef,
  useEffect,
  useMemo,
  useCallback,
  type KeyboardEvent,
} from 'react';
import { Input, Button, message, Modal, Select } from 'antd';
import { SendOutlined, StopOutlined } from '@ant-design/icons';
import {
  createDialogGenerateRequest,
  createProject,
  finalizeProjectBeacon,
  generateDialogContent,
  reportError,
  type UserInput,
} from '../services/api';
import AgentLogs from '../components/agent-logs';
import ProjectHistoryDrawer from '../components/project-history-drawer';
import ChatMessage from '../components/chat-message';
import ConversationTurn from '../components/conversation-turn';
import PendingTurn from '../components/pending-turn';
import { HistoryItem } from '../components/history-panel';
import { useBatchedState } from '../hooks/use-batched-state';
import { useSSEClient, type SSEConnectOptions } from '../hooks/use-sse-client';
import {
  isResumeFailedResult,
  isResumeFailureLogEvent,
  isResumeFailureStreamEvent,
  type StreamMessage,
} from '../utils/sse-resume';
import { createStreamIngestor } from '../utils/sse-stream-ingest';
import { formatDateTime } from '../utils/format';
import {
  bootstrapInitialConversation,
  switchHistoryProject,
} from '../utils/project-session-actions';
import {
  bindProjectId,
  clearProjectId,
  getOrCreateSessionId,
} from '../utils/session';
import {
  createInitialThread,
  type AgentLogEntry,
  type DialogResultData,
  type PendingThreadItem,
  type ThreadItem,
  type TurnThreadItem,
} from '../types/conversation';

const { TextArea } = Input;

type StreamEvent = StreamMessage & {
  type: 'log' | 'meta' | 'result';
};

type LogType = {
  agent_name: string;
  message: string;
  timestamp: string;
  agent_key?: string;
  intent?: string;
  intent_label?: string;
};

type GenerationSuccess = {
  kind: 'success';
  resultData: DialogResultData;
  userPrompt: string;
  sessionId: string;
  versionCount: number;
  pendingId: string;
};

type GenerationOutcome =
  | GenerationSuccess
  | { kind: 'cancelled' }
  | { kind: 'error'; error: string };

type GenerationDeps = {
  connect: <TMessage, TResult>(
    options: SSEConnectOptions<TMessage, TResult>,
  ) => Promise<TResult | null>;
  batchLogUpdate: (updater: (prev: LogType[]) => LogType[]) => void;
  flushLogs: () => void;
};

type GenerationPayload = {
  prompt: string;
  sessionId: string;
  projectId: string | null;
  versionCount: number;
  pendingId: string;
  getCancelled: () => boolean;
  deps: GenerationDeps;
  onSuccess: (outcome: GenerationSuccess) => void;
};

const runDialogGeneration = async (
  payload: GenerationPayload,
): Promise<GenerationOutcome> => {
  const { prompt, sessionId, projectId, getCancelled, deps } = payload;
  let streamResult: DialogResultData | null = null;

  const streamIngestor = createStreamIngestor();

  const enqueueLog = (from: string, text: string, extra?: Partial<LogType>) => {
    deps.batchLogUpdate((prev) => [
      ...prev,
      {
        agent_name: from,
        message: text,
        timestamp: new Date().toISOString(),
        ...extra,
      },
    ]);
  };

  const appendLog = (from: string, text: string, extra?: Partial<LogType>) => {
    console.log(`${from}: ${text}`);
    enqueueLog(from, text, extra);
  };

  try {
    const fallbackResult = await deps.connect<StreamEvent, DialogResultData>({
      createRequest: (signal, lastEventId) =>
        createDialogGenerateRequest(
          {
            prompt,
            session_id: sessionId,
            ...(projectId ? { project_id: projectId } : {}),
            ...(lastEventId ? { last_event_id: lastEventId } : {}),
          } satisfies UserInput,
          signal,
        ),
      parseMessage: (rawPayload) => JSON.parse(rawPayload) as StreamEvent,
      onReconnectAttempt: (attempt, lastEventId) => {
        streamIngestor.setResumeAfterEventId(
          attempt > 0 && lastEventId ? lastEventId : null,
        );
        if (attempt > 0) {
          message.info('连接恢复，正在续传…');
        }
      },
      onMessage: (event, eventId) => {
        if (isResumeFailureLogEvent(event) || isResumeFailureStreamEvent(event)) {
          if (isResumeFailureStreamEvent(event)) {
            streamResult = event.data as DialogResultData;
          }
          return;
        }

        streamIngestor.ingest(eventId, () => {
          if (event.type === 'log' && event.data && 'message' in event.data) {
            appendLog(event.data.from ?? '编排', event.data.message ?? '', {
              agent_key: event.data.agent_key,
              intent: event.data.intent,
              intent_label: event.data.intent_label,
            });
          } else if (event.type === 'result') {
            streamResult = event.data as DialogResultData;
          }
        });
      },
      fallback: async (error, lastEventId) => {
        console.warn('SSE 连接异常，已切换降级策略:', error);
        message.warning('实时通道异常，正在切换降级模式…');
        return generateDialogContent({
          request: {
            prompt,
            session_id: sessionId,
            ...(projectId ? { project_id: projectId } : {}),
            ...(lastEventId ? { last_event_id: lastEventId } : {}),
          },
          log_callback: appendLog,
          streamIngestor,
        });
      },
    });
    const resultData = fallbackResult ?? streamResult;

    if (isResumeFailedResult(resultData)) {
      return {
        kind: 'error',
        error: resultData.message ?? '续传失败，请重新发起生成',
      };
    }

    if (!resultData) {
      deps.flushLogs();
      if (getCancelled()) {
        return { kind: 'cancelled' };
      }
      return { kind: 'error', error: '未获取到生成结果' };
    }

    deps.flushLogs();
    return {
      kind: 'success',
      resultData,
      userPrompt: prompt,
      sessionId,
      versionCount: payload.versionCount,
      pendingId: payload.pendingId,
    };
  } catch (error) {
    console.error('Error generating content:', error);
    deps.flushLogs();
    if (getCancelled()) {
      return { kind: 'cancelled' };
    }
    reportError(error, 'dialog/generateContent', { prompt: payload.prompt });
    return {
      kind: 'error',
      error: error instanceof Error ? error.message : '生成内容失败',
    };
  }
};

const ensureProjectId = async (currentProjectId: string | null): Promise<string> => {
  if (currentProjectId) {
    return currentProjectId;
  }
  const created = await createProject();
  bindProjectId(created.project_id);
  return created.project_id;
};

const executeDialogGeneration = async (
  payload: GenerationPayload,
  onSettled: () => void,
): Promise<void> => {
  try {
    const outcome = await runDialogGeneration(payload);

    if (outcome.kind === 'success') {
      payload.onSuccess(outcome);
    } else if (outcome.kind === 'error') {
      message.error(outcome.error);
    }
  } finally {
    onSettled();
  }
};

type ScrollIntent = { type: 'bottom' } | { type: 'version'; versionId: number };

const DialogContent = () => {
  const [thread, setThread] = useState<ThreadItem[]>(createInitialThread);
  const [currentVersion, setCurrentVersion] = useState<number>(-1);
  const [inputValue, setInputValue] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationEpoch, setGenerationEpoch] = useState(0);
  const [currentSessionId, setCurrentSessionId] = useState(getOrCreateSessionId);
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const [isRestoring, setIsRestoring] = useState(true);
  const projectIdRef = useRef<string | null>(currentProjectId);
  const sessionIdRef = useRef(currentSessionId);

  const {
    state: logs,
    batchUpdate: batchLogUpdate,
    flushNow: flushLogs,
    resetState: resetLogs,
  } = useBatchedState<LogType[]>([]);
  const [finishTask, setFinishTask] = useState(false);
  const [, setHistory] = useState<HistoryItem[]>([]);
  const { connect, disconnect } = useSSEClient();
  const threadRef = useRef<HTMLDivElement>(null);
  const cancelByUserRef = useRef(false);
  const scrollIntentRef = useRef<ScrollIntent>({ type: 'bottom' });
  const generationLogsRef = useRef<AgentLogEntry[]>([]);

  const trackLogUpdate = useCallback(
    (updater: (prev: LogType[]) => LogType[]) => {
      batchLogUpdate((prev) => {
        const next = updater(prev);
        generationLogsRef.current = next.map(({ agent_name, message, timestamp }) => ({
          agent_name,
          message,
          timestamp,
        }));
        return next;
      });
    },
    [batchLogUpdate],
  );

  const completedTurns = useMemo(
    () => thread.filter((item): item is TurnThreadItem => item.type === 'turn'),
    [thread],
  );

  const pendingTurn = useMemo(
    () => thread.find((item): item is PendingThreadItem => item.type === 'pending'),
    [thread],
  );

  const versionOptions = useMemo(
    () =>
      completedTurns.map((turn) => ({
        id: turn.versionId,
        timestamp: turn.completedTimestamp,
        title: turn.result.title,
      })),
    [completedTurns],
  );

  const scrollToBottom = () => {
    const el = threadRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  };

  const scrollToVersion = (versionId: number) => {
    const container = threadRef.current;
    const anchor = document.getElementById(`version-anchor-${versionId}`);
    if (!container || !anchor) {
      return;
    }
    const offset = anchor.getBoundingClientRect().top - container.getBoundingClientRect().top;
    container.scrollTo({
      top: container.scrollTop + offset,
      behavior: 'smooth',
    });
  };

  useEffect(() => {
    const intent = scrollIntentRef.current;
    if (intent.type === 'version') {
      scrollToVersion(intent.versionId);
      return;
    }
    scrollToBottom();
  }, [thread, logs, isGenerating, currentVersion]);

  useEffect(() => {
    let cancelled = false;

    void bootstrapInitialConversation().then((result) => {
      if (cancelled) {
        return;
      }

      if (result.status === 'empty') {
        clearProjectId();
        setCurrentProjectId(null);
        setThread(createInitialThread());
        setCurrentVersion(-1);
        setIsRestoring(false);
        return;
      }

      if (result.status === 'error') {
        message.warning('无法加载历史对话，将开始新对话');
        clearProjectId();
        setCurrentProjectId(null);
        setThread(createInitialThread());
        setCurrentVersion(-1);
        setIsRestoring(false);
        return;
      }

      bindProjectId(result.projectId);
      setCurrentProjectId(result.projectId);
      setThread(result.thread);
      setCurrentVersion(result.latestVersionIndex);
      if (result.latestVersionIndex >= 0) {
        scrollIntentRef.current = {
          type: 'version',
          versionId: result.latestVersionIndex,
        };
      }
      setIsRestoring(false);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    projectIdRef.current = currentProjectId;
  }, [currentProjectId]);

  useEffect(() => {
    sessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  useEffect(() => {
    const onPageHide = () => {
      const projectId = projectIdRef.current;
      if (!projectId) {
        return;
      }
      finalizeProjectBeacon({
        project_id: projectId,
        session_id: sessionIdRef.current,
      });
    };

    window.addEventListener('pagehide', onPageHide);
    return () => window.removeEventListener('pagehide', onPageHide);
  }, []);

  useEffect(() => {
    if (!isGenerating) {
      return;
    }

    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };

    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [isGenerating]);

  const applyGenerationSuccess = (outcome: GenerationSuccess) => {
    const { resultData, userPrompt, sessionId, versionCount, pendingId } = outcome;
    const completedAt = Date.now();
    flushLogs();
    const capturedLogs = [...generationLogsRef.current];

    if (resultData.project_id) {
      bindProjectId(resultData.project_id);
      setCurrentProjectId(resultData.project_id);
    }

    setThread((prev) =>
      prev.map((item) => {
        if (item.type !== 'pending' || item.id !== pendingId) {
          return item;
        }
        const turn: TurnThreadItem = {
          type: 'turn',
          id: `turn_${versionCount}`,
          versionId: versionCount,
          userPrompt: item.userPrompt,
          userTimestamp: item.userTimestamp,
          result: resultData,
          completedTimestamp: completedAt,
          logs: capturedLogs,
        };
        return turn;
      }),
    );
    setCurrentVersion(versionCount);
    setFinishTask(true);
    scrollIntentRef.current = { type: 'version', versionId: versionCount };
    generationLogsRef.current = [];

    const historyItem: HistoryItem = {
      id: sessionId,
      userInput: userPrompt,
      timestamp: completedAt,
      title: resultData.title,
    };
    setHistory((prev) => [historyItem, ...prev]);
  };

  const startGeneration = (prompt: string) => {
    const trimmedPrompt = prompt.trim();
    if (!trimmedPrompt || pendingTurn || isRestoring) {
      return;
    }

    void (async () => {
      let projectId = currentProjectId;
      try {
        projectId = await ensureProjectId(projectId);
        if (projectId !== currentProjectId) {
          setCurrentProjectId(projectId);
        }
      } catch (error) {
        console.error('创建项目失败:', error);
        reportError(error, 'dialog/createProject');
        message.error('创建项目失败，请稍后重试');
        return;
      }

      cancelByUserRef.current = false;
      resetLogs([]);
      generationLogsRef.current = [];
      setFinishTask(false);

      const pendingId = `pending_${Date.now()}`;
      const pendingItem: PendingThreadItem = {
        type: 'pending',
        id: pendingId,
        userPrompt: trimmedPrompt,
        userTimestamp: Date.now(),
      };

      setThread((prev) => [...prev, pendingItem]);
      setInputValue('');
      setIsGenerating(true);
      setGenerationEpoch((epoch) => epoch + 1);
      scrollIntentRef.current = { type: 'bottom' };

      const versionCount = thread.filter(
        (item): item is TurnThreadItem => item.type === 'turn',
      ).length;

      void executeDialogGeneration(
        {
          prompt: trimmedPrompt,
          sessionId: currentSessionId,
          projectId,
          versionCount,
          pendingId,
          getCancelled: () => cancelByUserRef.current,
          deps: { connect, batchLogUpdate: trackLogUpdate, flushLogs },
          onSuccess: applyGenerationSuccess,
        },
        () => {
          setIsGenerating(false);
          setThread((prev) => {
            if (!prev.some((item) => item.type === 'pending')) {
              return prev;
            }
            return prev.filter((item) => item.type !== 'pending');
          });
        },
      );
    })();
  };

  const handleSubmit = () => {
    if (isGenerating) return;
    startGeneration(inputValue);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  };

  const handleStopGeneration = () => {
    Modal.confirm({
      title: '停止生成？',
      content: '当前任务将中断，已生成部分可能不完整。',
      okText: '停止',
      cancelText: '继续',
      onOk: () => {
        cancelByUserRef.current = true;
        disconnect();
        message.info('已停止当前生成任务');
      },
    });
  };

  const handleVersionSelect = (versionId: number) => {
    if (!completedTurns.some((turn) => turn.versionId === versionId)) {
      return;
    }
    setCurrentVersion(versionId);
    scrollIntentRef.current = { type: 'version', versionId };
  };

  const handleSelectHistoryProject = (projectId: string) => {
    if (isGenerating || isRestoring || projectId === currentProjectId) {
      return;
    }

    setIsRestoring(true);
    void switchHistoryProject(projectId).then((result) => {
      if (result.status === 'error') {
        message.error('加载对话失败，请稍后重试');
        setIsRestoring(false);
        return;
      }

      bindProjectId(result.projectId);
      setCurrentProjectId(result.projectId);
      setThread(result.loaded.thread);
      setCurrentVersion(result.loaded.latestVersionIndex);
      scrollIntentRef.current =
        result.loaded.latestVersionIndex >= 0
          ? { type: 'version', versionId: result.loaded.latestVersionIndex }
          : { type: 'bottom' };
      resetLogs([]);
      generationLogsRef.current = [];
      setInputValue('');
      setFinishTask(false);
      setIsRestoring(false);
    });
  };

  return (
    <main id="studio-main" className="chat-layout relative flex h-full min-h-0 flex-col">
      <a className="skip-link" href="#studio-thread">
        跳到对话内容
      </a>
      <header className="chat-header flex shrink-0 items-center gap-3 px-4 py-3 sm:gap-4 sm:px-6">
        <div className="min-w-0 flex-1">
          <h1 className="truncate font-display text-sm font-semibold tracking-wide text-ink sm:text-base">
            内容创作助手
          </h1>
          <p className="mt-0.5 truncate font-body text-xs italic text-ink-muted">
            多智能体协作 · 小红书图文生成
          </p>
        </div>
        <div className="flex max-w-[min(100%,18rem)] shrink-0 items-center gap-2 sm:max-w-none">
          {versionOptions.length > 0 && (
            <>
              <label
                className="hidden font-display text-[0.65rem] uppercase tracking-widest text-gold-dark sm:inline"
                htmlFor="version-select"
              >
                版本
              </label>
              <Select
                id="version-select"
                aria-label="文案版本"
                value={currentVersion >= 0 ? currentVersion : undefined}
                onChange={handleVersionSelect}
                className="min-w-[10rem] sm:min-w-[12rem]"
                placeholder="选择版本"
                size="middle"
              >
                {versionOptions.map((version) => (
                  <Select.Option key={version.id} value={version.id}>
                    V{version.id + 1} · {formatDateTime(version.timestamp)}
                    {version.title ? ` · ${version.title}` : ''}
                  </Select.Option>
                ))}
              </Select>
            </>
          )}
          <ProjectHistoryDrawer
            currentProjectId={currentProjectId}
            onSelectProject={(projectId) => {
              void handleSelectHistoryProject(projectId);
            }}
            disabled={isGenerating || isRestoring}
          />
        </div>
      </header>

      <div
        ref={threadRef}
        id="studio-thread"
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label="对话记录"
        className="chat-thread min-h-0 flex-1 overflow-y-auto"
      >
        <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
          {isRestoring && (
            <p className="mb-4 text-center font-body text-sm italic text-ink-muted">
              正在恢复上次会话…
            </p>
          )}
          {thread.map((item) => {
            if (item.type === 'welcome') {
              return (
                <div key={item.id} className="turn-segment turn-segment--welcome">
                  <ChatMessage
                    role="assistant"
                    content={item.content}
                    timestamp={item.timestamp}
                  />
                </div>
              );
            }

            if (item.type === 'turn') {
              return (
                <ConversationTurn
                  key={item.id}
                  turn={item}
                  isActive={currentVersion === item.versionId}
                />
              );
            }

            if (item.type === 'pending') {
              return (
                <PendingTurn key={item.id} pending={item}>
                  <AgentLogs
                    key={`${generationEpoch}-${finishTask}`}
                    logs={logs}
                    isCollapse={false}
                    isLoading={isGenerating}
                    title="思考过程"
                    variant="embedded"
                  />
                </PendingTurn>
              );
            }

            return null;
          })}
        </div>
      </div>

      <div className="chat-composer px-4 py-4 sm:px-6">
        <div className="mx-auto w-full max-w-3xl">
          <div className="chat-composer-box overflow-hidden rounded-sm">
            <label className="sr-only" htmlFor="studio-prompt">
              描述你想创作的小红书内容
            </label>
            <TextArea
              id="studio-prompt"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="描述你想创作的小红书内容…（Enter 发送，Shift+Enter 换行）"
              autoSize={{ minRows: 1, maxRows: 6 }}
              disabled={isGenerating || isRestoring}
              aria-describedby="studio-prompt-hint"
            />
            <div className="flex items-center justify-between gap-2 border-t border-gold/15 px-3 py-2">
              <p
                id="studio-prompt-hint"
                className="font-body text-xs italic text-ink-muted"
              >
                {isRestoring
                  ? '正在恢复上次会话…'
                  : isGenerating
                    ? '生成中…，可随时停止'
                    : `${completedTurns.length > 0 ? `已有 ${completedTurns.length} 个版本 · ` : ''}新消息将出现在上一轮结果下方`}
              </p>
              <div className="flex shrink-0 gap-2">
                {isGenerating ? (
                  <Button
                    danger
                    type="primary"
                    size="small"
                    icon={<StopOutlined />}
                    onClick={handleStopGeneration}
                    className="!font-display !text-xs !uppercase !tracking-wider"
                  >
                    停止
                  </Button>
                ) : (
                  <Button
                    type="primary"
                    size="small"
                    icon={<SendOutlined />}
                    onClick={handleSubmit}
                    disabled={
                      !inputValue.trim() || Boolean(pendingTurn) || isRestoring
                    }
                    className="!font-display !text-xs !uppercase !tracking-wider"
                  >
                    发送
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
};

export default DialogContent;
