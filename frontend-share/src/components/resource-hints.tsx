import { preconnect, prefetchDNS } from 'react-dom';

import { getGlobalResourceOrigins } from '@/lib/resource-hints';

/** 在 SSR 阶段注入 dns-prefetch / preconnect（React 19 resource hint API） */
export const ResourceHints = () => {
  for (const origin of getGlobalResourceOrigins()) {
    prefetchDNS(origin);
    preconnect(origin, { crossOrigin: 'anonymous' });
  }

  return null;
};
