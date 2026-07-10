"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  FireOutlined,
  LinkOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  List,
  Space,
  Spin,
  Tag,
  App,
} from 'antd';
import {
  reportError,
  streamSocialHotspotsAnalyze,
  type HotspotAnalysisResult,
  type HotspotItem,
  type HotspotPlatform,
  type HotspotSSEMessage,
} from '@/services/api';

const ALL_PLATFORMS: HotspotPlatform[] = ['weibo', 'xhs', 'douyin', 'x', 'reddit'];

const PLATFORM_LABELS: Record<HotspotPlatform, string> = {
  weibo: '微博',
  xhs: '小红书',
  douyin: '抖音',
  x: 'X（Twitter）',
  reddit: 'Reddit',
};

const emptyHotspots = (): Record<HotspotPlatform, HotspotItem[]> => ({
  weibo: [],
  xhs: [],
  douyin: [],
  x: [],
  reddit: [],
});

const formatGeneratedAt = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('zh-CN', { hour12: false });
};

const SocialHotspotAnalysis = () => {
  const { message } = App.useApp();
  const messageRef = useRef(message);
  messageRef.current = message;

  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [platformHotspots, setPlatformHotspots] = useState(emptyHotspots);
  const [summary, setSummary] = useState('');
  const [crossPlatform, setCrossPlatform] = useState<string[]>([]);
  const [insights, setInsights] = useState<string[]>([]);
  const [dataSourceNotes, setDataSourceNotes] = useState('');
  const [result, setResult] = useState<HotspotAnalysisResult | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleStreamEvent = useCallback((event: HotspotSSEMessage) => {
    const { type, data } = event;
    switch (type) {
      case 'log': {
        const text = String(data.message ?? '');
        if (text) {
          setLogs((prev) => [...prev, text]);
        }
        break;
      }
      case 'platform_hotspots': {
        const platform = data.platform as HotspotPlatform;
        if (!platform) {
          break;
        }
        setPlatformHotspots((prev) => ({
          ...prev,
          [platform]: (data.hotspots as HotspotItem[]) ?? [],
        }));
        break;
      }
      case 'summary':
        setSummary(String(data.summary ?? ''));
        break;
      case 'cross_platform':
        setCrossPlatform((data.items as string[]) ?? []);
        break;
      case 'insights':
        setInsights((data.items as string[]) ?? []);
        break;
      case 'data_source':
        setDataSourceNotes(String(data.notes ?? ''));
        break;
      case 'result':
        setResult(data as unknown as HotspotAnalysisResult);
        break;
      case 'error':
        setStreamError(String(data.message ?? '分析失败'));
        break;
      default:
        break;
    }
  }, []);

  const handleStreamEventRef = useRef(handleStreamEvent);
  handleStreamEventRef.current = handleStreamEvent;

  const runStreamAnalysis = useCallback(async (controller: AbortController) => {
    setLoading(true);
    setStreamError(null);
    setLogs([]);
    setPlatformHotspots(emptyHotspots());
    setSummary('');
    setCrossPlatform([]);
    setInsights([]);
    setDataSourceNotes('');
    setResult(null);

    try {
      let hadStreamError = false;
      const finalResult = await streamSocialHotspotsAnalyze({
        payload: {},
        signal: controller.signal,
        onEvent: (event) => {
          if (event.type === 'error') {
            hadStreamError = true;
          }
          handleStreamEventRef.current(event);
        },
      });
      if (controller.signal.aborted) {
        return;
      }
      if (finalResult) {
        setResult(finalResult);
        messageRef.current.success('热点速报已更新');
      } else if (!hadStreamError) {
        messageRef.current.warning('未收到完整分析结果');
      }
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      await reportError(error, 'hotspot/stream');
      const errorMessage = error instanceof Error ? error.message : '热点分析失败';
      setStreamError(errorMessage);
      messageRef.current.error(errorMessage);
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, []);

  const startAnalysis = useCallback(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    void runStreamAnalysis(controller);
  }, [runStreamAnalysis]);

  useEffect(() => {
    const controller = new AbortController();
    abortRef.current = controller;
    void runStreamAnalysis(controller);

    return () => {
      controller.abort();
    };
  }, [runStreamAnalysis]);

  const displayHotspots = (platform: HotspotPlatform) =>
    platformHotspots[platform]?.length
      ? platformHotspots[platform]
      : (result?.hotspots.filter((item) => item.platform === platform) ?? []);

  const partialErrors = result?.partial_errors ?? {};
  const latestLog = logs[logs.length - 1];

  return (
    <div className="flex h-full min-h-0 flex-col overflow-auto p-4 md:p-6">
      <div className="atelier-panel-frame mb-4 flex flex-wrap items-center justify-between gap-3 rounded-sm border border-gold/35 bg-[rgba(250,243,232,0.97)] px-4 py-3">
        <div>
          <p className="atelier-eyebrow text-gold">Hotspot Brief</p>
          <div className="mt-1 flex items-center gap-2">
            <FireOutlined className="text-gold-dark" aria-hidden="true" />
            <h1 className="font-display text-lg font-semibold tracking-wide text-ink">
              商品宣传热点速报
            </h1>
          </div>
        </div>
        <Button
          type="default"
          icon={<ReloadOutlined aria-hidden="true" />}
          loading={loading}
          onClick={startAnalysis}
        >
          刷新
        </Button>
      </div>

      {streamError && (
        <Alert className="mb-4" type="error" showIcon title={streamError} />
      )}

      {loading && (
        <Card className="atelier-panel-frame mb-4 rounded-sm border border-gold/35" size="small">
          <Space orientation="vertical" className="w-full" size="small">
            <div className="flex items-center gap-2">
              <Spin size="small" />
              <span className="font-body text-sm text-ink-muted">
                {latestLog ?? '大模型正在分析各平台商品宣传热点…'}
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {ALL_PLATFORMS.map((platform) => {
                const hotspotCount = displayHotspots(platform).length;
                let status = '待分析';
                if (hotspotCount > 0) {
                  status = `已分析 ${hotspotCount} 条`;
                } else if (loading && logs.some((line) => line.includes(PLATFORM_LABELS[platform]))) {
                  status = '分析中';
                }
                return (
                  <Tag key={platform} color={hotspotCount > 0 ? 'gold' : 'default'}>
                    {PLATFORM_LABELS[platform]}：{status}
                  </Tag>
                );
              })}
            </div>
          </Space>
        </Card>
      )}

      {Object.keys(partialErrors).length > 0 && (
        <Alert
          className="mb-4"
          type="warning"
          showIcon
          title={`部分平台检索失败：${Object.keys(partialErrors).join('、')}`}
        />
      )}

      {summary && (
        <Card
          className="atelier-panel-frame mb-4 rounded-sm border border-gold/35"
          title="📈 商品宣传多平台热点速报"
          extra={
            result?.generated_at ? (
              <span className="font-body text-xs italic text-ink-muted">
                {formatGeneratedAt(result.generated_at)}
              </span>
            ) : null
          }
          size="small"
        >
          <p className="font-body text-sm leading-relaxed text-ink">{summary}</p>
        </Card>
      )}

      <div className="mb-4 grid gap-4 md:grid-cols-2">
        {ALL_PLATFORMS.map((platform, index) => {
          const items = displayHotspots(platform);
          const analyzing =
            loading &&
            items.length === 0 &&
            logs.some((line) => line.includes(PLATFORM_LABELS[platform]));
          const showCard = items.length > 0 || analyzing || loading;
          if (!showCard) {
            return null;
          }
          return (
            <Card
              key={platform}
              className="atelier-panel-frame rounded-sm border border-gold/35"
              title={
                <div className="flex items-center gap-2">
                  <Tag color="gold">{index + 1}</Tag>
                  <Tag color="gold">{PLATFORM_LABELS[platform]}</Tag>
                  {analyzing && <Spin size="small" />}
                </div>
              }
              size="small"
            >
              {items.length > 0 ? (
                <List
                  dataSource={items}
                  renderItem={(item, itemIndex) => (
                    <List.Item key={item.id}>
                      <div className="w-full font-body text-sm text-ink">
                        <div className="mb-1 font-semibold leading-snug">
                          {itemIndex + 1}. {item.title}
                          {item.suspicious && (
                            <Tag color="warning" className="ml-2">
                              ⚠️ 存疑
                            </Tag>
                          )}
                        </div>
                        {item.summary && (
                          <p className="mb-1 text-xs leading-relaxed text-ink-muted">
                            {item.summary}
                          </p>
                        )}
                        {item.promotion_relevance && (
                          <p className="mb-2 text-xs text-gold-dark">
                            宣传关联：{item.promotion_relevance}
                          </p>
                        )}
                        {item.source_url && (
                          <a
                            href={item.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-gold-dark underline decoration-gold/40 underline-offset-2 hover:text-burgundy-dark"
                            aria-label={`查看 ${item.title} 来源`}
                          >
                            <LinkOutlined aria-hidden="true" />
                            查看来源
                          </a>
                        )}
                      </div>
                    </List.Item>
                  )}
                />
              ) : (
                <p className="font-body text-xs italic text-ink-muted">
                  {analyzing ? '大模型分析中…' : '等待分析…'}
                </p>
              )}
            </Card>
          );
        })}
      </div>

      {crossPlatform.length > 0 && (
        <Card
          className="atelier-panel-frame mb-4 rounded-sm border border-gold/35"
          title="🔗 跨平台共性商品热点"
          size="small"
        >
          <List
            dataSource={crossPlatform}
            renderItem={(item, index) => (
              <List.Item key={`${index}-${item.slice(0, 24)}`}>
                <span className="font-body text-sm leading-relaxed text-ink">
                  {index + 1}. {item}
                </span>
              </List.Item>
            )}
          />
        </Card>
      )}

      {insights.length > 0 && (
        <Card
          className="atelier-panel-frame mb-4 rounded-sm border border-gold/35"
          title="🧠 营销价值洞察"
          size="small"
        >
          <List
            dataSource={insights}
            renderItem={(item, index) => (
              <List.Item key={`${index}-${item.slice(0, 24)}`}>
                <span className="font-body text-sm leading-relaxed text-ink">
                  {index + 1}. {item}
                </span>
              </List.Item>
            )}
          />
        </Card>
      )}

      {dataSourceNotes && (
        <Card
          className="atelier-panel-frame rounded-sm border border-gold/35"
          title="📌 数据来源及可信度说明"
          size="small"
        >
          <p className="font-body text-sm leading-relaxed text-ink-muted">{dataSourceNotes}</p>
        </Card>
      )}
    </div>
  );
};

export default SocialHotspotAnalysis;
