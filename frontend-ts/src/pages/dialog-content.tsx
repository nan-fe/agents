import { useState, useRef, useEffect, useMemo } from 'react';
import {
  Layout,
  Input,
  Button,
  Space,
  message,
  Typography,
  Select,
  Card,
} from 'antd';
import {
  SendOutlined,
  HistoryOutlined,
  StopOutlined,
} from '@ant-design/icons';
import {
  createDialogGenerateRequest,
  generateDialogContent,
  type UserInput,
} from '../services/api';
import { List, RowComponentProps, useListRef } from 'react-window';
import AgentLogs from '../components/agent-logs';
import ResultDisplay from '../components/result-display';
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

const { Header, Content } = Layout;
const { Text, Paragraph, Title } = Typography;

interface Message {
  id: string;
  type: 'user' | 'system';
  content: string;
  timestamp: number;
}

interface Version {
  id: number;
  timestamp: number;
  content: string;
  title: string;
  hashtags: string[];
  imageUrl: string;
}

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

interface MessageRowData {
  messages: Message[];
}

const MESSAGE_BASE_HEIGHT = 56;
const MESSAGE_LINE_HEIGHT = 24;
const MESSAGE_CHARS_PER_LINE = 18;
const MESSAGE_MAX_HEIGHT = 640;
const SESSION_STORAGE_KEY = 'xhs_session_id';

const WELCOME_MESSAGE_CONTENT =
  '哈喽～我是你的内容创作助手 小H，你可以输入内容描述（例如：推荐一款适合学生党的平价防晒霜，清爽不油腻）我将生成一段图文给你发小红书';

const createWelcomeMessage = (): Message => ({
  id: 'msg_welcome',
  type: 'system',
  content: WELCOME_MESSAGE_CONTENT,
  timestamp: Date.now(),
});

const getOrCreateSessionId = (): string => {
  const sessionStorageId = sessionStorage.getItem(SESSION_STORAGE_KEY);
  const localStorageId = localStorage.getItem(SESSION_STORAGE_KEY);
  const stableId = sessionStorageId || localStorageId;

  if (stableId) {
    if (!sessionStorageId) {
      sessionStorage.setItem(SESSION_STORAGE_KEY, stableId);
    }
    if (!localStorageId) {
      localStorage.setItem(SESSION_STORAGE_KEY, stableId);
    }
    return stableId;
  }

  const newId = `session_${Date.now()}`;
  sessionStorage.setItem(SESSION_STORAGE_KEY, newId);
  localStorage.setItem(SESSION_STORAGE_KEY, newId);
  return newId;
};

const createInitialMessages = (): Message[] => [createWelcomeMessage()];

type DialogResultData = {
  content: string;
  title: string;
  hashtags: string[];
  image_url: string;
  message?: string;
  error_code?: string;
};

type GenerationSuccess = {
  kind: 'success';
  resultData: DialogResultData;
  userPrompt: string;
  sessionId: string;
  versionCount: number;
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
  versionCount: number;
  getCancelled: () => boolean;
  deps: GenerationDeps;
  onSuccess: (outcome: GenerationSuccess) => void;
};

const runDialogGeneration = async (
  payload: GenerationPayload,
): Promise<GenerationOutcome> => {
  const { prompt, sessionId, versionCount, getCancelled, deps } = payload;
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
        message.warning('实时通道异常，正在切换降级模式...');
        return generateDialogContent({
          request: {
            prompt,
            session_id: sessionId,
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
      versionCount,
    };
  } catch (error) {
    console.error('Error generating content:', error);
    deps.flushLogs();
    if (getCancelled()) {
      return { kind: 'cancelled' };
    }
    return {
      kind: 'error',
      error: error instanceof Error ? error.message : '生成内容失败',
    };
  }
};

// SSE 流式生成不适合包在 useActionState 里（会延迟中间 state 提交），用模块级 async 执行。
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

const estimateMessageRowHeight = (content: string) => {
  const lineCount = content
    .split('\n')
    .reduce((total, line) => total + Math.max(1, Math.ceil(line.length / MESSAGE_CHARS_PER_LINE)), 0);

  return MESSAGE_BASE_HEIGHT + lineCount * MESSAGE_LINE_HEIGHT;
};

const MessageRow = ({ index, style, messages }: RowComponentProps<MessageRowData>) => {
  const messageItem = messages[index];

  return (
    <div style={style} className="box-border pb-2">
      <div className="flex h-full flex-col box-border border-b border-gray-100 pb-2">
        <Text strong>{messageItem.type === 'user' ? '用户' : '系统'}</Text>
        <Paragraph className="!mb-1">{messageItem.content}</Paragraph>
        <Text type="secondary" className="text-xs">
          {new Date(messageItem.timestamp).toLocaleString()}
        </Text>
      </div>
    </div>
  );
};

const DialogContent = () => {
  const [messages, setMessages] = useState(createInitialMessages);
  const [versions, setVersions] = useState<Version[]>([]);
  const [currentVersion, setCurrentVersion] = useState<number>(-1);
  const [inputValue, setInputValue] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationEpoch, setGenerationEpoch] = useState(0);
  const [currentSessionId] = useState(getOrCreateSessionId);
  
  const {
    state: logs,
    batchUpdate: batchLogUpdate,
    flushNow: flushLogs,
    resetState: resetLogs,
  } = useBatchedState<LogType[]>([]);
  const [result, setResult] = useState<any>(null);
  const [finishTask, setFinishTask] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const { connect, disconnect } = useSSEClient();
  const virtualListRef = useListRef(null);
  const messageViewportRef = useRef<HTMLDivElement>(null);
  const [viewportHeight, setViewportHeight] = useState(MESSAGE_MAX_HEIGHT);
  const messageRowHeights = useMemo(
    () => messages.map((item) => estimateMessageRowHeight(item.content)),
    [messages],
  );

  const cancelByUserRef = useRef(false);

  useEffect(() => {
    if (messages.length === 0) return;
    virtualListRef.current?.scrollToRow({
      align: 'end',
      index: messages.length - 1,
    });
  }, [messages, virtualListRef]);

  useEffect(() => {
    const container = messageViewportRef.current;
    if (!container) return;

    const syncHeight = () => {
      setViewportHeight(container.clientHeight || MESSAGE_MAX_HEIGHT);
    };

    syncHeight();
    const observer = new ResizeObserver(syncHeight);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const applyGenerationSuccess = (outcome: GenerationSuccess) => {
    const { resultData, userPrompt, sessionId, versionCount } = outcome;

    setResult(resultData);

    const systemMessage: Message = {
      id: `msg_${Date.now() + 1}`,
      type: 'system',
      content: '已生成内容，请查看下方文案区域',
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, systemMessage]);
    setFinishTask(true);

    const newVersion: Version = {
      id: versionCount,
      timestamp: Date.now(),
      content: resultData.content,
      title: resultData.title,
      hashtags: resultData.hashtags,
      imageUrl: resultData.image_url,
    };
    setVersions((prev) => [...prev, newVersion]);
    setCurrentVersion(newVersion.id);

    const historyItem: HistoryItem = {
      id: sessionId,
      userInput: userPrompt,
      timestamp: Date.now(),
      title: resultData.title,
    };
    setHistory((prev) => [historyItem, ...prev]);
  };

  const startGeneration = (prompt: string) => {
    const trimmedPrompt = prompt.trim();
    if (!trimmedPrompt) {
      return;
    }

    cancelByUserRef.current = false;
    resetLogs([]);
    setFinishTask(false);

    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      type: 'user',
      content: trimmedPrompt,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsGenerating(true);
    setGenerationEpoch((epoch) => epoch + 1);

    void executeDialogGeneration(
      {
        prompt: trimmedPrompt,
        sessionId: currentSessionId,
        versionCount: versions.length,
        getCancelled: () => cancelByUserRef.current,
        deps: { connect, batchLogUpdate, flushLogs },
        onSuccess: applyGenerationSuccess,
      },
      () => setIsGenerating(false),
    );
  };

  const handleSubmit = () => {
    startGeneration(inputValue);
  };

  const handleStopGeneration = () => {
    cancelByUserRef.current = true;
    disconnect();
    message.info('已停止当前生成任务');
  };

  const handleVersionSelect = (versionId: number) => {
    const version = versions[versionId];
    setCurrentVersion(versionId);
    setResult({
      title: version.title,
      content: version.content,
      hashtags: version.hashtags,
      image_url: version.imageUrl,
    });

    const systemMessage: Message = {
      id: `msg_${Date.now()}`,
      type: 'system',
      content: `已切换至版本 V${versionId + 1}`,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, systemMessage]);

    message.success(`已切换至版本 V${versionId + 1}`);
  };

  return (
    <Layout className="min-h-full">
      <Header className="bg-white px-4 shadow-md">
        <Title level={4} className="!my-4">
          内容创作助手
        </Title>
      </Header>
      <Layout className="min-h-0">
        <Content className="flex w-full min-w-0">
          <div className="flex w-full min-w-0 flex-col gap-4 lg:h-[calc(100vh-160px)] lg:flex-row">
            {/* 历史记录面板 */}
            {/* <HistoryPanel
              history={history}
              onSelectHistory={handleSelectHistory}
              onDeleteHistory={handleDeleteHistory}
              currentSessionId={currentSessionId}
            /> */}
            
            {/* 聊天窗口 */}
            <Card
              title="聊天记录"
              className="flex min-h-[360px] w-full flex-col lg:h-full lg:w-[min(420px,36vw)] lg:flex-shrink-0 [&_.ant-card-body]:flex [&_.ant-card-body]:min-h-0 [&_.ant-card-body]:flex-1 [&_.ant-card-body]:flex-col"
            >
              <div ref={messageViewportRef} className="flex-1 min-h-0 mb-4">
                <List
                  rowComponent={MessageRow}
                  rowCount={messages.length}
                  rowHeight={(index) => messageRowHeights[index] ?? MESSAGE_BASE_HEIGHT}
                  rowProps={{ messages }}
                  overscanCount={2}
                  style={{ height: viewportHeight, width: '100%' }}
                  listRef={virtualListRef}
                />
              </div>

              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder="请输入您的需求..."
                  onPressEnter={handleSubmit}
                  className="flex-1"
                />
                <Space>
                  {isGenerating ? (
                    <Button
                      danger
                      type="primary"
                      icon={<StopOutlined />}
                      onClick={handleStopGeneration}
                    >
                      停止生成
                    </Button>
                  ) : (
                    <Button
                      type="primary"
                      icon={<SendOutlined />}
                      onClick={handleSubmit}
                      disabled={isGenerating}
                    >
                      发送
                    </Button>
                  )}
                </Space>
              </div>
            </Card>

            {/* 右侧内容区 */}
            <div className="flex min-w-0 flex-1 flex-col overflow-x-hidden lg:h-full lg:overflow-y-auto">
              {/* 版本选择器 */}
              <Card title="文案版本" extra={<HistoryOutlined />}>
                <Select
                  value={currentVersion}
                  onChange={handleVersionSelect}
                  className="w-full"
                  placeholder="选择版本"
                >
                  {versions.map((version) => (
                    <Select.Option key={version.id} value={version.id}>
                      V{version.id + 1} -{" "}
                      {new Date(version.timestamp).toLocaleString()}
                    </Select.Option>
                  ))}
                </Select>
              </Card>

              {/* 生成结果展示 */}
              {result ? (
                <Card title="生成结果" className="mt-4">
                  <ResultDisplay result={result} />
                </Card>
              ) : null}

              {/* Agent 日志 */}
              <AgentLogs
                key={`${generationEpoch}-${finishTask}`}
                logs={logs}
                isCollapse={finishTask}
                isLoading={isGenerating}
              />
            </div>
          </div>
        </Content>
      </Layout>
    </Layout>
  );
};

export default DialogContent;
