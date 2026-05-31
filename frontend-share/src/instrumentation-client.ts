import * as Sentry from '@sentry/nextjs';

import { getSentryInitOptions } from './lib/sentry';

Sentry.init(getSentryInitOptions());

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
