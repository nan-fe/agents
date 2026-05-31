import { preconnect, prefetchDNS, preload } from 'react-dom';

/** 分享页主图：dns-prefetch + preconnect + preload */
export const preloadShareImage = (imageUrl: string) => {
  const origin = (() => {
    try {
      return new URL(imageUrl).origin;
    } catch {
      return null;
    }
  })();

  if (origin) {
    prefetchDNS(origin);
    preconnect(origin, { crossOrigin: 'anonymous' });
  }

  preload(imageUrl, { as: 'image' });
};
