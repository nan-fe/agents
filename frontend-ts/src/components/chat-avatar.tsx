type ChatAvatarProps = {
  role: 'user' | 'assistant';
};

const ChatAvatar = ({ role }: ChatAvatarProps) => {
  const isUser = role === 'user';

  return (
    <div
      className={`chat-avatar flex h-9 w-9 shrink-0 items-center justify-center rounded-sm font-display text-xs font-semibold ${
        isUser
          ? 'bg-burgundy/90 text-ivory'
          : 'border border-gold/50 bg-ivory text-gold-dark'
      }`}
      aria-hidden="true"
    >
      {isUser ? '我' : 'H'}
    </div>
  );
};

export default ChatAvatar;
