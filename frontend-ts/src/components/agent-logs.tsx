import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import { DownOutlined, UpOutlined } from '@ant-design/icons';
import { formatTimestamp } from '../utils/helper';
import type { AgentLogEntry } from '../types/conversation';

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

interface IAgentLog {
  logs: AgentLogEntry[];
  title?: string;
  isCollapse?: boolean;
  isLoading?: boolean;
  variant?: 'default' | 'embedded';
}

const AgentLogs = (param: IAgentLog) => {
  const {
    logs,
    title = '思考过程',
    isCollapse = false,
    isLoading = false,
    variant = 'default',
  } = param;
  const [expanded, setExpanded] = useState(!isCollapse);
  const bodyRef = useRef<HTMLDivElement>(null);
  const isEmbedded = variant === 'embedded';
  const showThinking = isLoading && logs.length > 0;

  const scrollToLatest = useCallback(() => {
    const body = bodyRef.current;
    if (!body) {
      return;
    }
    body.scrollTo({
      top: body.scrollHeight,
      behavior: prefersReducedMotion() ? 'auto' : 'smooth',
    });
  }, []);

  useLayoutEffect(() => {
    if (!expanded) {
      return;
    }
    scrollToLatest();
  }, [expanded, logs, isLoading, scrollToLatest]);

  if (logs.length === 0 && !isLoading) {
    return null;
  }

  const lastLogIndex = logs.length - 1;

  return (
    <div
      className={
        isEmbedded ? 'agent-logs agent-logs--embedded' : 'agent-logs atelier-agent-collapse'
      }
    >
      <div className="agent-logs__panel">
        <button
          type="button"
          className="agent-logs__toggle"
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
        >
          <span className="agent-logs__title">
            <span className="agent-logs__title-main">
              {isLoading ? '正在整理思路…' : title}
            </span>
            <span className="agent-logs__title-hint">非成稿，仅作过程参考</span>
            <span className="sr-only">{expanded ? '，收起' : '，展开'}</span>
          </span>
          <span className="agent-logs__chevron" aria-hidden="true">
            {expanded ? (
              <UpOutlined className="agent-logs__chevron-icon" />
            ) : (
              <DownOutlined className="agent-logs__chevron-icon" />
            )}
          </span>
        </button>

        {expanded && (
          <div ref={bodyRef} className="agent-logs__body">
            {logs.length === 0 ? (
              <ol className="agent-logs__steps" aria-label="思考步骤">
                <li className="agent-logs__step agent-logs__step--current">
                  <div className="agent-logs__step-rail" aria-hidden="true">
                    <span className="agent-logs__step-node agent-logs__step-node--pulse" />
                  </div>
                  <div className="agent-logs__step-content">
                    <p className="agent-logs__step-message agent-logs__step-message--waiting">
                      多智能体正在协作…
                    </p>
                  </div>
                </li>
              </ol>
            ) : (
              <ol className="agent-logs__steps" aria-label="思考步骤">
                {logs.map((log, index) => {
                  const isCurrent = isLoading && index === lastLogIndex;
                  const isDone = !isCurrent;

                  return (
                    <li
                      key={`${log.timestamp}-${log.agent_name}-${index}`}
                      className={`agent-logs__step ${isDone ? 'agent-logs__step--done' : ''} ${isCurrent ? 'agent-logs__step--current' : ''}`}
                    >
                      <div className="agent-logs__step-rail" aria-hidden="true">
                        <span
                          className={`agent-logs__step-node ${isCurrent ? 'agent-logs__step-node--pulse' : ''}`}
                        />
                        {(index < lastLogIndex || showThinking) && (
                          <span className="agent-logs__step-line" />
                        )}
                      </div>
                      <div className="agent-logs__step-content">
                        <div className="agent-logs__step-meta">
                          <span className="agent-logs__step-agent">{log.agent_name}</span>
                          <time
                            className="agent-logs__step-time"
                            dateTime={new Date(log.timestamp).toISOString()}
                          >
                            {formatTimestamp(log.timestamp)}
                          </time>
                        </div>
                        <p className="agent-logs__step-message">{log.message}</p>
                      </div>
                    </li>
                  );
                })}
                {showThinking && (
                  <li
                    className="agent-logs__step agent-logs__step--current"
                    aria-busy="true"
                  >
                    <div className="agent-logs__step-rail" aria-hidden="true">
                      <span className="agent-logs__step-node agent-logs__step-node--pulse" />
                    </div>
                    <div className="agent-logs__step-content">
                      <p className="agent-logs__step-message agent-logs__step-message--waiting">
                        继续构思中…
                      </p>
                    </div>
                  </li>
                )}
              </ol>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default AgentLogs;
