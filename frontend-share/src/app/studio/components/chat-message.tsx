"use client";
import type { ReactNode } from 'react';

import { formatTimestamp } from '../../../lib/timestamp';
import ChatAvatar from './chat-avatar';

type ChatMessageProps = {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  children?: ReactNode;
};

const ChatMessage = ({ role, content, timestamp, children }: ChatMessageProps) => {
  const isUser = role === 'user';

  return (
    <article
      aria-label={isUser ? '你的消息' : '助手小H的消息'}
      className={`chat-message flex w-full gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      <ChatAvatar role={role} />
      <div
        className={`flex min-w-0 max-w-[min(100%,42rem)] flex-1 flex-col ${isUser ? 'items-end' : 'items-start'}`}
      >
        <div
          className={
            isUser ? 'chat-bubble chat-bubble-user' : 'chat-bubble chat-bubble-assistant'
          }
        >
          {content ? (
            <p className="whitespace-pre-wrap font-body text-base leading-relaxed">{content}</p>
          ) : null}
          {children}
        </div>
        <time
          className={`mt-1.5 font-body text-xs italic text-ink-muted/80 ${isUser ? 'text-right' : 'text-left'}`}
          dateTime={new Date(timestamp).toISOString()}
        >
          {formatTimestamp(timestamp)}
        </time>
      </div>
    </article>
  );
};

export default ChatMessage;
