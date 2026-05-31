import type { BrowserOptions, EdgeOptions, NodeOptions } from '@sentry/nextjs';

type SentryInitOptions = NodeOptions | BrowserOptions | EdgeOptions;

/** Better Stack DSN: https://$TOKEN@$INGESTING_HOST/1 (see Better Stack Data ingestion tab) */
export const getSentryDsn = (): string | undefined => {
  const dsn = process.env.SENTRY_DSN ?? process.env.NEXT_PUBLIC_SENTRY_DSN;
  return dsn && dsn.length > 0 ? dsn : undefined;
};

export const isSentryEnabled = (): boolean => Boolean(getSentryDsn());

export const getSentryInitOptions = (): SentryInitOptions => {
  const enabled = isSentryEnabled();

  return {
    dsn: getSentryDsn(),
    enabled,
    environment: process.env.SENTRY_ENVIRONMENT ?? process.env.NODE_ENV,
    tracesSampleRate: enabled
      ? Number(
          process.env.SENTRY_TRACES_SAMPLE_RATE ?? 1
        )
      : 0,
    initialScope: {
      tags: {
        application: process.env.SENTRY_APPLICATION_ID ?? 'frontend-share',
      },
    },
    sendDefaultPii: false,
  };
};
