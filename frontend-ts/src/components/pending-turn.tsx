import type { ReactNode } from 'react';

import ChatMessage from './chat-message';
import ChatAvatar from './chat-avatar';
import type { PendingThreadItem } from '../types/conversation';

type PendingTurnProps = {
  pending: PendingThreadItem;
  children?: ReactNode;
};

const PendingTurn = ({ pending, children }: PendingTurnProps) => (
  <div className="turn-segment turn-segment--pending" aria-busy="true">
    <div className="turn-segment__user">
      <ChatMessage
        role="user"
        content={pending.userPrompt}
        timestamp={pending.userTimestamp}
      />
    </div>

    <section className="assistant-reply assistant-reply--pending" aria-label="小H 正在创作">
      <div className="assistant-reply__row">
        <ChatAvatar role="assistant" />
        <div className="assistant-reply__content">{children}</div>
      </div>
    </section>
  </div>
);

export default PendingTurn;
