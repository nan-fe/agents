const getOriginFromUrl = (url: string): string | null => {
  try {
    return new URL(url).origin;
  } catch {
    return null;
  }
};

const uniqueOrigins = (origins: Array<string | null | undefined>): string[] => [
  ...new Set(origins.filter((origin): origin is string => Boolean(origin))),
];

/** 全站可预连接的外部 origin（Better Stack / Sentry 等） */
export const getGlobalResourceOrigins = (): string[] =>
  uniqueOrigins([
    getOriginFromUrl(process.env.NEXT_PUBLIC_SENTRY_DSN ?? ''),
    getOriginFromUrl(process.env.SENTRY_DSN ?? ''),
  ]);

export const getImageResourceOrigin = (imageUrl: string): string | null =>
  getOriginFromUrl(imageUrl);
