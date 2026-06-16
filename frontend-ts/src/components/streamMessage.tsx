import { useEffect, useRef, useState } from 'react';

type StreamMessageProps = {
  streamContent: string;
  className?: string;
  /** bubble：聊天气泡样式；inline：继承父级排版（如思考日志） */
  variant?: 'bubble' | 'inline';
};

/** 打字效果的文本展示组件 */
const StreamMessage = ({
  streamContent,
  className,
  variant = 'inline',
}: StreamMessageProps) => {
  const [content, setContent] = useState('');
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const curIndexRef = useRef(0);

  const clearAnimation = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  useEffect(() => {
    clearAnimation();
    if (content.length > streamContent.length) {
      setContent('');
      curIndexRef.current = 0;
      if (!streamContent.length) {
        return;
      }
    }
    if (curIndexRef.current === streamContent.length) {
      return;
    }

    let startIndex = content.length;
    if (!streamContent.startsWith(content)) {
      setContent('');
      startIndex = 0;
    }

    curIndexRef.current = startIndex;
    timerRef.current = setInterval(() => {
      const nextIdx = curIndexRef.current + 1;
      if (nextIdx <= streamContent.length) {
        setContent(streamContent.slice(0, nextIdx));
        curIndexRef.current = nextIdx;
      } else {
        clearAnimation();
      }
    }, 50);

    return () => clearAnimation();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 仅随 streamContent 重置打字动画
  }, [streamContent]);

  const resolvedClassName =
    variant === 'bubble'
      ? ['streaming-message-bubble', className].filter(Boolean).join(' ')
      : className;

  if (variant === 'bubble') {
    return <div className={resolvedClassName}>{content}</div>;
  }

  return <p className={resolvedClassName}>{content}</p>;
};

export default StreamMessage;
