import type { MetadataRoute } from 'next';

const robots = (): MetadataRoute.Robots => {
  const siteUrl =
    process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, '') ?? undefined;

  return {
    rules: {
      userAgent: '*',
      allow: ['/'],
    },
    ...(siteUrl ? { host: siteUrl.replace(/^https?:\/\//, '') } : {}),
  };
};

export default robots;
