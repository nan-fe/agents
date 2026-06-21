"use client";
import AgentLogs from './agent-logs';
import ChatAvatar from './chat-avatar';
import ChatMessage from './chat-message';
import ResultDisplay from './result-display';
import FeishuPushPrompt from './feishu-push-prompt';
import type { TurnThreadItem } from '../../../types/conversation';

type ConversationTurnProps = {
  turn: TurnThreadItem;
  isActive: boolean;
};

const ConversationTurn = ({ turn, isActive }: ConversationTurnProps) => (
  <div className="turn-segment" id={`version-anchor-${turn.versionId}`}>
    <h2 className="sr-only">版本 {turn.versionId + 1}</h2>

    <div className="turn-segment__user">
      <ChatMessage
        role="user"
        content={turn.userPrompt}
        timestamp={turn.userTimestamp}
      />
    </div>

    <section
      className={`assistant-reply ${isActive ? 'assistant-reply--active' : ''}`}
      aria-label="小H 的回复"
    >
      <div className="assistant-reply__row">
        <ChatAvatar role="assistant" />
        <div className="assistant-reply__content">
          {turn.logs.length > 0 && (
            <AgentLogs
              logs={turn.logs}
              isCollapse
              isLoading={false}
              title="思考过程"
              variant="embedded"
            />
          )}
          <ResultDisplay result={turn.result} variant="minimal" />
          <FeishuPushPrompt result={turn.result} />
        </div>
      </div>
    </section>
  </div>
);

export default ConversationTurn;
