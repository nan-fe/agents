import type { BrowserOptions, EdgeOptions, NodeOptions } from '@sentry/nextjs';

type SentryInitOptions = NodeOptions | BrowserOptions | EdgeOptions;

const DEFAULT_SENTRY_DSN =
  'https://DYwAS6KnxQkz9CnaCzMWiLNh@s2461160.eu-nbg-2.betterstackdata.com/2461176';

/** Better Stack DSN: https://$TOKEN@$INGESTING_HOST/1 (see Better Stack Data ingestion tab) */
export const getSentryDsn = (): string | undefined => {
  const dsn = process.env.SENTRY_DSN ?? process.env.NEXT_PUBLIC_SENTRY_DSN ?? DEFAULT_SENTRY_DSN;
  return dsn && dsn.length > 0 ? dsn : undefined;
};

export const isSentryEnabled = (): boolean => Boolean(getSentryDsn());

const getDefaultTracesSampleRate = (): number => {
  if (process.env.SENTRY_TRACES_SAMPLE_RATE) {
    return Number(process.env.SENTRY_TRACES_SAMPLE_RATE);
  }
  return process.env.NODE_ENV === 'development' ? 1 : 0.1;
};

export const getSentryInitOptions = (): SentryInitOptions => {
  const enabled = isSentryEnabled();

  return {
    dsn: getSentryDsn(),
    enabled,
    environment: process.env.SENTRY_ENVIRONMENT ?? process.env.NODE_ENV,
    tracesSampleRate: enabled ? getDefaultTracesSampleRate() : 0,
    initialScope: {
      tags: {
        application: process.env.SENTRY_APPLICATION_ID ?? 'frontend-share',
      },
    },
    sendDefaultPii: false,
  };
};
